from rest_framework import serializers

from apps.company.models import (
    Company,
    CompanyMember,
    CompanyRole,
    is_valid_tax_id,
    normalize_tax_id,
)


class CompanySerializer(serializers.ModelSerializer):
    """
    Serializa y valida los datos de una compañía.

    @version 1.1
    @author Agustin
    """

    my_role = serializers.CharField(read_only=True)

    class Meta:
        model = Company
        fields = (
            "id",
            "my_role",
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


class CompanyMemberRoleSerializer(serializers.Serializer):
    """
    Valida un rol existente para una membresía de Company.

    @version 1.0
    @author Agustin
    """

    role = serializers.CharField(max_length=20)

    def validate_role(self, value):
        """
        Resuelve el código de rol contra los roles registrados.

        @version 1.0
        @author Agustin
        """
        if value not in ("owner", "member"):
            raise serializers.ValidationError("Rol inválido.")
        role = CompanyRole.objects.filter(code=value).first()
        if role is None:
            raise serializers.ValidationError("Rol inválido.")
        return role


class CompanyMemberCreateSerializer(CompanyMemberRoleSerializer):
    """
    Valida un usuario por UUID o correo y el rol para agregar una membresía.

    @version 1.1
    @author Agustin
    """

    email = serializers.EmailField(required=False)
    user_id = serializers.UUIDField(required=False)
    role = serializers.CharField(max_length=20, required=False, default="member")

    def validate_email(self, value):
        """
        Elimina espacios exteriores antes de resolver el correo.

        @version 1.0
        @author Agustin
        """
        return value.strip()

    def validate(self, attrs):
        """
        Exige exactamente un identificador del usuario objetivo.

        @version 1.0
        @author Agustin
        """
        has_email = "email" in attrs
        has_user_id = "user_id" in attrs
        if has_email and has_user_id:
            raise serializers.ValidationError(
                {"email": "Indique email o user_id, pero no ambos."}
            )
        if not has_email and not has_user_id:
            raise serializers.ValidationError(
                {"email": "Este campo o user_id es obligatorio."}
            )
        return attrs


class CompanyMemberSerializer(serializers.ModelSerializer):
    """
    Expone sólo los datos de identificación y rol de un miembro.

    @version 1.0
    @author Agustin
    """

    user_id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(
        source="user.email",
        read_only=True,
        allow_null=True,
    )
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    role = serializers.CharField(source="role.code", read_only=True)

    class Meta:
        model = CompanyMember
        fields = ("user_id", "email", "first_name", "last_name", "role")
