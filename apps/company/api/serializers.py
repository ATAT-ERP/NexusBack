from rest_framework import serializers

from apps.company.models import Company, is_valid_tax_id, normalize_tax_id


class CompanySerializer(serializers.ModelSerializer):
    """
    Serializa y valida los datos de una compañía.

    @version 1.0
    @author Agustin
    """

    class Meta:
        model = Company
        fields = (
            "id",
            "type",
            "name",
            "legal_name",
            "tax_id",
            "email",
            "phone",
            "address_street",
            "address_number",
            "address_city",
            "address_postal_code",
            "address_province",
            "address_country",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "is_active",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {
            "type": {
                "error_messages": {
                    "invalid_choice": "Tipo de compañía inválido.",
                },
            },
        }

    def to_internal_value(self, data):
        data = data.copy()
        if "tax_id" in data:
            data["tax_id"] = normalize_tax_id(data["tax_id"]) or None
        return super().to_internal_value(data)

    def validate_tax_id(self, value):
        if value and not is_valid_tax_id(value):
            raise serializers.ValidationError("El CUIT informado no es válido.")
        return value
