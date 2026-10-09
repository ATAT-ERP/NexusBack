from decimal import ROUND_HALF_UP, Decimal

from apps.billing.enums.tax import TaxTreatment, VATRate

CENT = Decimal("0.01")

VAT_RATE_PERCENTAGES = {
    VATRate.ZERO: Decimal("0"),
    VATRate.TWO_AND_HALF: Decimal("2.5"),
    VATRate.FIVE: Decimal("5"),
    VATRate.TEN_AND_HALF: Decimal("10.5"),
    VATRate.TWENTY_ONE: Decimal("21"),
    VATRate.TWENTY_SEVEN: Decimal("27"),
}


def round_amount(value):
    """
    Redondea un importe a 2 decimales con ROUND_HALF_UP. Es la única política
    de redondeo de Billing: todo importe calculado debe pasar por esta función.
    @version 1.0
    @author Uziel
    """
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_item_amounts(quantity, unit_price, discount, tax_treatment, vat_rate=None):
    """
    Calcula los importes de un ítem a partir de valores Decimal, sin acceder
    a la base. El descuento es un porcentaje y se aplica sobre el subtotal.
    El IVA se calcula sobre el neto sólo si el tratamiento es gravado; en los
    demás casos vale 0 y la alícuota se ignora. Cada importe se redondea con
    round_amount.
    @version 1.0
    @author Uziel
    """
    subtotal = round_amount(quantity * unit_price)
    discount_amount = round_amount(subtotal * discount / 100)
    net = subtotal - discount_amount

    if tax_treatment == TaxTreatment.TAXED:
        vat = round_amount(net * VAT_RATE_PERCENTAGES[vat_rate] / 100)
    else:
        vat = Decimal("0.00")

    return {
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "net": net,
        "vat": vat,
        "total": net + vat,
    }


def calculate_invoice_totals(items):
    """
    Calcula los totales de una factura a partir de una lista de ítems. Cada
    ítem es un dict con los argumentos de calculate_item_amounts (quantity,
    unit_price, discount, tax_treatment y, opcionalmente, vat_rate).
    Los ítems no gravados y los que no discriminan IVA se agrupan en
    net_untaxed. El IVA es la suma del IVA ya calculado por ítem, por lo que
    admite alícuotas distintas. Cada total se redondea con round_amount.
    Devuelve un dict para poder sumar otros tributos sin cambiar su forma.
    @version 1.0
    @author Uziel
    """
    net_taxed = net_untaxed = net_exempt = vat_amount = Decimal("0.00")

    for item in items:
        amounts = calculate_item_amounts(**item)
        vat_amount += amounts["vat"]
        if item["tax_treatment"] == TaxTreatment.TAXED:
            net_taxed += amounts["net"]
        elif item["tax_treatment"] == TaxTreatment.EXEMPT:
            net_exempt += amounts["net"]
        else:
            net_untaxed += amounts["net"]

    net_taxed = round_amount(net_taxed)
    net_untaxed = round_amount(net_untaxed)
    net_exempt = round_amount(net_exempt)
    vat_amount = round_amount(vat_amount)

    return {
        "net_taxed": net_taxed,
        "net_untaxed": net_untaxed,
        "net_exempt": net_exempt,
        "vat_amount": vat_amount,
        "total": round_amount(net_taxed + net_untaxed + net_exempt + vat_amount),
    }
