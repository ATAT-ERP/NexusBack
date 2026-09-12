from rest_framework import serializers

from apps.company.models import Company, is_valid_tax_id, normalize_tax_id


class CompanyCreateSerializer(serializers.ModelSerializer):
    optional_text_fields = (
        "legal_name",
        "phone",
        "address_street",
        "address_number",
        "address_city",
        "address_postal_code",
        "address_province",
        "address_country",
    )

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
        )
        read_only_fields = ("id",)

    def to_internal_value(self, data):
        validated = super().to_internal_value(data)
        for field in self.optional_text_fields:
            if validated.get(field) == "":
                validated[field] = None
        return validated

    def validate_type(self, value):
        if value not in Company.Type.values:
            raise serializers.ValidationError("Tipo de compañía inválido.")
        return value

    def validate_email(self, value):
        if value:
            return value.lower()
        return value

    def validate_tax_id(self, value):
        if value is None or value == "":
            return None

        normalized = normalize_tax_id(value)
        if not normalized:
            return None

        if not is_valid_tax_id(normalized):
            raise serializers.ValidationError("El CUIT informado no es válido.")

        if Company.objects.filter(tax_id=normalized).exists():
            raise serializers.ValidationError(
                "Ya existe una compañía registrada con ese CUIT."
            )

        return normalized


class CompanyUpdateSerializer(serializers.ModelSerializer):
    optional_text_fields = (
        "legal_name",
        "phone",
        "address_street",
        "address_number",
        "address_city",
        "address_postal_code",
        "address_province",
        "address_country",
    )

    class Meta:
        model = Company
        fields = (
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
        )
        read_only_fields = ()

    def to_internal_value(self, data):
        validated = super().to_internal_value(data)
        for field in self.optional_text_fields:
            if validated.get(field) == "":
                validated[field] = None
        return validated

    def validate_type(self, value):
        if value not in Company.Type.values:
            raise serializers.ValidationError("Tipo de compañía inválido.")
        return value

    def validate_email(self, value):
        if value:
            return value.lower()
        return value

    def validate_tax_id(self, value):
        if value is None or value == "":
            return None

        normalized = normalize_tax_id(value)
        if not normalized:
            return None

        if not is_valid_tax_id(normalized):
            raise serializers.ValidationError("El CUIT informado no es válido.")

        current_tax_id = getattr(self.instance, "tax_id", None)
        if current_tax_id != normalized:
            if Company.objects.filter(tax_id=normalized).exists():
                raise serializers.ValidationError(
                    "Ya existe una compañía registrada con ese CUIT."
                )

        return normalized


class CompanySerializer(serializers.ModelSerializer):
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
        read_only_fields = fields
