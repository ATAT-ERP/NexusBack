from django.core.exceptions import ValidationError

from apps.billing.enums.invoice import InvoiceConcept, InvoiceType
from apps.billing.enums.tax import TaxTreatment, VATCondition, VATRate


def validate_quantity(quantity):
    """
    Rechaza una cantidad que no sea mayor a 0.
    @version 1.0
    @author Uziel
    """
    if quantity <= 0:
        raise ValidationError({"quantity": "La cantidad debe ser mayor a 0."})


def validate_unit_price(unit_price):
    """
    Rechaza un precio unitario negativo.
    @version 1.0
    @author Uziel
    """
    if unit_price < 0:
        raise ValidationError({"unit_price": "El precio unitario no puede ser negativo."})


def validate_discount(discount):
    """
    Rechaza un descuento fuera del rango de 0 a 100. Repite el constraint del
    modelo para informar el error antes de llegar a la base.
    @version 1.0
    @author Uziel
    """
    if not 0 <= discount <= 100:
        raise ValidationError({"discount": "El descuento debe estar entre 0 y 100."})


def validate_vat_rate(vat_rate):
    """
    Rechaza una alícuota informada que no pertenezca a VATRate.
    @version 1.0
    @author Uziel
    """
    if vat_rate is not None and vat_rate not in VATRate.values:
        raise ValidationError({"vat_rate": "La alícuota de IVA no es válida."})


def validate_tax_treatment_and_vat_rate(tax_treatment, vat_rate):
    """
    Valida la coherencia entre tratamiento fiscal y alícuota: un ítem gravado
    exige una alícuota válida y cualquier otro tratamiento no puede tenerla.
    @version 1.0
    @author Uziel
    """
    if tax_treatment == TaxTreatment.TAXED:
        if vat_rate is None:
            raise ValidationError(
                {"vat_rate": "La alícuota de IVA es obligatoria para ítems gravados."}
            )
        validate_vat_rate(vat_rate)
    elif vat_rate is not None:
        raise ValidationError(
            {"vat_rate": "Este tratamiento fiscal no admite alícuota de IVA."}
        )


def validate_item(quantity, unit_price, discount, tax_treatment, vat_rate=None):
    """
    Aplica todas las reglas de un ítem. Debe ejecutarse antes de
    calculate_item_amounts para que un ítem inválido no llegue al cálculo.
    @version 1.0
    @author Uziel
    """
    validate_quantity(quantity)
    validate_unit_price(unit_price)
    validate_discount(discount)
    validate_vat_rate(vat_rate)
    validate_tax_treatment_and_vat_rate(tax_treatment, vat_rate)


def validate_concept_dates(concept, service_date_from, service_date_to):
    """
    Valida las fechas según el concepto del comprobante. Para productos no
    exige nada; para servicios, o productos y servicios, exige ambas fechas
    de servicio y que la fecha desde no sea posterior a la fecha hasta.
    @version 1.0
    @author Uziel
    """
    if concept == InvoiceConcept.PRODUCTS:
        return

    if service_date_from is None or service_date_to is None:
        raise ValidationError(
            {"service_date_from": "Las fechas de servicio son obligatorias para este concepto."}
        )
    if service_date_from > service_date_to:
        raise ValidationError(
            {"service_date_to": "La fecha hasta no puede ser anterior a la fecha desde."}
        )


def validate_invoice_type(invoice_type, issuer_vat_condition, receiver_vat_condition):
    """
    Valida que el tipo de comprobante sea posible para la condición frente al
    IVA del emisor y del receptor. El Responsable Inscripto emite A a
    Responsables Inscriptos o a cualquier variante de Monotributo (MONOTAX,
    SOCIAL_MONOTAX, PROMOTED_INDEPENDENT_WORKER), y B al resto; los emisores
    Monotributistas o Exentos sólo emiten C. Toda otra combinación se rechaza.
    @version 1.1
    @author Uziel
    """
    invoice_type = InvoiceType(invoice_type)
    issuer = VATCondition(issuer_vat_condition)
    receiver = VATCondition(receiver_vat_condition)

    if issuer == VATCondition.REGISTERED_RESPONSIBLE:
        receives_a = receiver in (
            VATCondition.REGISTERED_RESPONSIBLE,
            VATCondition.MONOTAX,
            VATCondition.SOCIAL_MONOTAX,
            VATCondition.PROMOTED_INDEPENDENT_WORKER,
        )
        if invoice_type == InvoiceType.INVOICE_A and receives_a:
            return
        if invoice_type == InvoiceType.INVOICE_B and not receives_a:
            return
    elif issuer in (
        VATCondition.MONOTAX,
        VATCondition.SOCIAL_MONOTAX,
        VATCondition.PROMOTED_INDEPENDENT_WORKER,
        VATCondition.EXEMPT,
    ):
        if invoice_type == InvoiceType.INVOICE_C:
            return

    raise ValidationError(
        {
            "invoice_type": (
                f"{invoice_type.label} no es válida para un emisor "
                f"{issuer.label} con un receptor {receiver.label}."
            )
        }
    )
