from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.billing.enums.invoice import (
    INVOICE_TYPE_BY_CREDIT_NOTE_TYPE,
    DocumentType,
    InvoiceStatus,
)
from apps.billing.models import CreditNote, CreditNoteInvoice, Invoice, InvoiceTax
from apps.billing.services import rules
from apps.billing.services.calculations import (
    calculate_invoice_totals,
    calculate_vat_tax_details,
)
from apps.billing.services.numbering import next_invoice_number
from apps.company.models import is_valid_tax_id

UPDATED_FIELDS = (
    "status",
    "number",
    "issue_date",
    "net_taxed",
    "net_untaxed",
    "net_exempt",
    "vat_amount",
    "total",
    "issuer_legal_name",
    "issuer_tax_id",
    "issuer_address",
    "issuer_vat_condition",
    "issuer_gross_income",
    "issuer_activity_start_date",
    "updated_at",
)

CREDIT_NOTE_UPDATED_FIELDS = (
    *UPDATED_FIELDS,
    "receiver_name",
    "receiver_vat_condition",
    "receiver_document_type",
    "receiver_document_number",
    "receiver_address",
)


def issue_invoice(invoice):
    """
    Emite un comprobante en borrador dentro de una única transacción:
    valida, recalcula, obtiene el correlativo, copia el snapshot del
    emisor, fija número y fecha, guarda los totales finales, genera el
    detalle de IVA por alícuota y cambia el estado a ISSUED. Si cualquier
    paso falla se revierte todo, incluido el incremento del correlativo.
    La fila de la factura se bloquea para que dos emisiones simultáneas de
    la misma factura no convivan.
    @version 1.1
    @author Thiago
    """
    with transaction.atomic():
        invoice = (
            Invoice.objects.select_for_update(of=("self",))
            .select_related("point_of_sale__fiscal_profile__company")
            .get(pk=invoice.pk)
        )
        point_of_sale = invoice.point_of_sale
        fiscal_profile = point_of_sale.fiscal_profile
        company = fiscal_profile.company
        items = list(invoice.items.all())
        issue_date = timezone.localdate()

        _validate_invoice(invoice, fiscal_profile, company, items, issue_date)
        item_values = [_item_values(item) for item in items]
        totals = calculate_invoice_totals(item_values)

        invoice.number = next_invoice_number(point_of_sale, invoice.invoice_type)
        invoice.issue_date = issue_date
        _copy_issuer_snapshot(invoice, company, fiscal_profile)
        for field, value in totals.items():
            setattr(invoice, field, value)
        invoice.status = InvoiceStatus.ISSUED
        invoice.save(update_fields=UPDATED_FIELDS)

        InvoiceTax.objects.bulk_create(
            InvoiceTax(invoice=invoice, **detail)
            for detail in calculate_vat_tax_details(item_values)
        )

        return invoice


def issue_credit_note(credit_note):
    """
    Emite una Nota de Crédito en borrador dentro de una única transacción.
    Bloquea la NC y luego sus facturas (por pk, para evitar deadlocks),
    valida, calcula los totales de la NC y de cada factura asociada con el
    motor de calculations.py y verifica que ninguna supere el saldo
    disponible de su factura. Fija número, fecha y snapshots de emisor y
    receptor, guarda el total de cada asociación y pasa a CANCELLED las
    facturas que quedan totalmente acreditadas. Si cualquier paso falla se
    revierte todo, incluido el incremento del correlativo.
    @version 1.0
    @author Uziel
    """
    with transaction.atomic():
        credit_note = (
            CreditNote.objects.select_for_update(of=("self",))
            .select_related("point_of_sale__fiscal_profile__company")
            .get(pk=credit_note.pk)
        )
        point_of_sale = credit_note.point_of_sale
        fiscal_profile = point_of_sale.fiscal_profile
        company = fiscal_profile.company
        invoices = {
            invoice.pk: invoice
            for invoice in Invoice.objects.select_for_update(of=("self",))
            .filter(credit_note_invoices__credit_note=credit_note)
            .order_by("pk")
        }
        associations = list(
            credit_note.credit_note_invoices.prefetch_related("items").order_by("pk")
        )

        _validate_credit_note(credit_note, company, invoices, associations)

        values_by_association = [
            [_item_values(item) for item in association.items.all()]
            for association in associations
        ]
        totals = calculate_invoice_totals(
            [values for group in values_by_association for values in group]
        )
        credited = dict(
            CreditNoteInvoice.objects.filter(
                invoice__in=invoices.keys(), credit_note__status=InvoiceStatus.ISSUED
            )
            .values("invoice")
            .annotate(credited=Sum("total"))
            .values_list("invoice", "credited")
        )
        for association, values in zip(associations, values_by_association):
            association.total = calculate_invoice_totals(values)["total"]
            _validate_credit_limit(
                association, invoices[association.invoice_id], credited
            )

        first_invoice = invoices[associations[0].invoice_id]
        credit_note.number = next_invoice_number(
            point_of_sale, credit_note.credit_note_type
        )
        credit_note.issue_date = timezone.localdate()
        _copy_issuer_snapshot(credit_note, company, fiscal_profile)
        credit_note.receiver_name = first_invoice.receiver_name
        credit_note.receiver_vat_condition = first_invoice.receiver_vat_condition
        credit_note.receiver_document_type = first_invoice.receiver_document_type
        credit_note.receiver_document_number = first_invoice.receiver_document_number
        credit_note.receiver_address = first_invoice.receiver_address
        for field, value in totals.items():
            setattr(credit_note, field, value)
        credit_note.status = InvoiceStatus.ISSUED
        credit_note.save(update_fields=CREDIT_NOTE_UPDATED_FIELDS)

        CreditNoteInvoice.objects.bulk_update(associations, ["total"])
        for association in associations:
            invoice = invoices[association.invoice_id]
            previous = credited.get(invoice.pk, Decimal("0.00"))
            if previous + association.total == invoice.total:
                invoice.status = InvoiceStatus.CANCELLED
                invoice.save(update_fields=["status", "updated_at"])

        return credit_note


def _copy_issuer_snapshot(document, company, fiscal_profile):
    """
    Copia al comprobante los datos del emisor vigentes al momento de la
    emisión, para que no cambien si luego se edita la Company.
    @version 1.0
    @author Uziel
    """
    document.issuer_legal_name = company.legal_name
    document.issuer_tax_id = company.tax_id
    document.issuer_address = _format_address(company)
    document.issuer_vat_condition = fiscal_profile.vat_condition
    document.issuer_gross_income = fiscal_profile.gross_income
    document.issuer_activity_start_date = fiscal_profile.business_start_date


def _item_values(item):
    return {
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "discount": item.discount,
        "tax_treatment": item.tax_treatment,
        "vat_rate": item.vat_rate,
    }


def _format_address(company):
    street = " ".join(filter(None, [company.address_street, company.address_number]))
    parts = [street, company.address_city, company.address_province]
    return ", ".join(filter(None, parts))[:255]


def _validate_invoice(invoice, fiscal_profile, company, items, issue_date):
    if invoice.status != InvoiceStatus.DRAFT:
        raise ValidationError({"status": "Sólo se puede emitir un comprobante en borrador."})
    if not invoice.point_of_sale.is_active:
        raise ValidationError({"point_of_sale": "El punto de venta no está activo."})

    _validate_issuer_data(company)

    if not items:
        raise ValidationError({"items": "El comprobante debe tener al menos un ítem."})
    for item in items:
        rules.validate_item(**_item_values(item))
        rules.validate_vat_discrimination(invoice.invoice_type, item.tax_treatment)

    _validate_receiver(invoice)
    rules.validate_invoice_type(
        invoice.invoice_type,
        fiscal_profile.vat_condition,
        invoice.receiver_vat_condition,
    )
    rules.validate_concept_dates(
        invoice.concept, invoice.service_date_from, invoice.service_date_to
    )
    if invoice.due_date is not None and invoice.due_date < issue_date:
        raise ValidationError(
            {"due_date": "La fecha de vencimiento no puede ser anterior a la de emisión."}
        )


def _validate_credit_note(credit_note, company, invoices, associations):
    """
    Valida que la Nota de Crédito pueda emitirse: borrador, punto de venta
    activo, emisor completo, facturas asociadas emitidas e ítems válidos para
    el tipo de factura homólogo.
    @version 1.0
    @author Uziel
    """
    if credit_note.status != InvoiceStatus.DRAFT:
        raise ValidationError(
            {"status": "Sólo se puede emitir una Nota de Crédito en borrador."}
        )
    if not credit_note.point_of_sale.is_active:
        raise ValidationError({"point_of_sale": "El punto de venta no está activo."})

    _validate_issuer_data(company)

    if not associations:
        raise ValidationError(
            {"invoices": "La Nota de Crédito debe tener al menos una factura asociada."}
        )
    if any(invoice.status != InvoiceStatus.ISSUED for invoice in invoices.values()):
        raise ValidationError(
            {"invoices": "Todas las facturas asociadas deben estar emitidas."}
        )

    invoice_type = INVOICE_TYPE_BY_CREDIT_NOTE_TYPE[credit_note.credit_note_type]
    for association in associations:
        items = list(association.items.all())
        if not items:
            raise ValidationError(
                {"items": f"La factura {association.invoice_id} debe tener al menos un ítem."}
            )
        for item in items:
            rules.validate_item(**_item_values(item))
            rules.validate_vat_discrimination(invoice_type, item.tax_treatment)


def _validate_credit_limit(association, invoice, credited):
    """
    Exige que el total de la asociación sea positivo y no supere el saldo
    de la factura, es decir su total menos lo ya acreditado por Notas de
    Crédito emitidas.
    @version 1.0
    @author Uziel
    """
    if association.total <= 0:
        raise ValidationError(
            {"items": f"El total acreditado de la factura {invoice.pk} debe ser mayor a 0."}
        )
    available = invoice.total - credited.get(invoice.pk, Decimal("0.00"))
    if association.total > available:
        raise ValidationError(
            {
                "items": (
                    f"El total acreditado de la factura {invoice.pk} "
                    f"({association.total}) supera su saldo disponible ({available})."
                )
            }
        )


def _validate_issuer_data(company):
    missing = []
    if not company.legal_name:
        missing.append("razón social")
    if not is_valid_tax_id(company.tax_id):
        missing.append("CUIT válido")
    if not company.address_street:
        missing.append("calle")
    if not company.address_city:
        missing.append("ciudad")
    if missing:
        raise ValidationError(
            {"company": f"La compañía debe completar: {', '.join(missing)}."}
        )


def _validate_receiver(invoice):
    if not invoice.receiver_name.strip():
        raise ValidationError({"receiver_name": "El receptor debe tener nombre."})

    number = invoice.receiver_document_number.strip()
    if invoice.receiver_document_type in (DocumentType.CUIT, DocumentType.CUIL):
        valid = is_valid_tax_id(number)
    else:
        valid = number.isdigit()
    if not valid:
        raise ValidationError(
            {"receiver_document_number": "El documento del receptor no es válido."}
        )