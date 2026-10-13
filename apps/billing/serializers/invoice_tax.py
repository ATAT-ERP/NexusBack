from rest_framework import serializers

from apps.billing.models import InvoiceTax


class InvoiceTaxSerializer(serializers.ModelSerializer):
    """
    Expone un tributo de un comprobante. Es de sólo lectura: el backend lo
    deriva de los ítems al emitir la factura.
    @version 1.0
    @author Antonio
    """

    class Meta:
        model = InvoiceTax
        fields = (
            "id",
            "tax_type",
            "vat_rate",
            "base_amount",
            "amount",
        )
        read_only_fields = fields
