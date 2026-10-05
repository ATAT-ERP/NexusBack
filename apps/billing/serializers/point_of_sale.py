from rest_framework import serializers

from apps.billing.models import PointOfSale


class PointOfSaleSerializer(serializers.ModelSerializer):
    """
    Expone el punto de venta con su número representado en cinco
    dígitos. El número es de solo lectura: se asigna automáticamente,
    nunca se recibe desde la API.
    @version 1.0
    @author Thiago
    """

    number = serializers.CharField(source="formatted_number", read_only=True)

    class Meta:
        model = PointOfSale
        fields = ("id", "fiscal_profile", "number", "is_active", "created_at", "updated_at")
        read_only_fields = ("fiscal_profile", "number", "created_at", "updated_at")