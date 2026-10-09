from rest_framework import serializers

from apps.billing.models import InvoiceItem


class InvoiceItemSerializer(serializers.ModelSerializer):
    """
    Valida y expone un ítem de comprobante. La factura se asocia desde la
    view, nunca desde el body.
    @version 1.0
    @author Uziel
    """

    class Meta:
        model = InvoiceItem
        fields = (
            "id",
            "invoice",
            "description",
            "quantity",
            "unit_price",
            "discount",
            "tax_treatment",
            "vat_rate",
        )
        read_only_fields = ("id", "invoice")
