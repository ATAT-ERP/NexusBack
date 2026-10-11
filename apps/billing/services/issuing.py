from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.billing.enums.invoice import DocumentType, InvoiceStatus
from apps.billing.models import Invoice
from apps.billing.services import rules
from apps.billing.services.calculations import calculate_invoice_totals
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


def issue_invoice(invoice):
    """
    Emite un comprobante en borrador dentro de una única transacción:
    valida, recalcula, obtiene el correlativo, copia el snapshot del
    emisor, fija número y fecha, guarda los totales finales y cambia el
    estado a ISSUED. Si cualquier paso falla se revierte todo, incluido
    el incremento del correlativo. La fila de la factura se bloquea para
    que dos emisiones simultáneas de la misma factura no convivan.
    @version 1.0
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
        totals = calculate_invoice_totals([_item_values(item) for item in items])

        invoice.number = next_invoice_number(point_of_sale, invoice.invoice_type)
        invoice.issue_date = issue_date
        invoice.issuer_legal_name = company.legal_name
        invoice.issuer_tax_id = company.tax_id
        invoice.issuer_address = _format_address(company)
        invoice.issuer_vat_condition = fiscal_profile.vat_condition
        invoice.issuer_gross_income = fiscal_profile.gross_income
        invoice.issuer_activity_start_date = fiscal_profile.business_start_date
        for field, value in totals.items():
            setattr(invoice, field, value)
        invoice.status = InvoiceStatus.ISSUED
        invoice.save(update_fields=UPDATED_FIELDS)

        return invoice


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