from rest_framework import serializers

from apps.accounting.enums import AccountType
from apps.accounting.models import Account


class AccountSerializer(serializers.ModelSerializer):
    """
    Serializa cuentas y valida códigos únicos dentro de su Company.

    @version 1.0
    @author Agustin
    """

    class Meta:
        model = Account
        fields = (
            "id",
            "company",
            "code",
            "name",
            "account_type",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("company",)

    def validate_code(self, value):
        """
        Rechaza un código ya asignado a otra cuenta de la Company.

        @version 1.0
        @author Agustin
        """
        company_id = self.context["view"].kwargs["company_id"]
        accounts = Account.objects.filter(company_id=company_id, code=value)
        if self.instance is not None:
            accounts = accounts.exclude(pk=self.instance.pk)
        if accounts.exists():
            raise serializers.ValidationError(
                "Ya existe una cuenta con este código en la compañía."
            )
        return value


class AccountListQuerySerializer(serializers.Serializer):
    """
    Valida los filtros del plan de cuentas.

    @version 1.0
    @author Agustin
    """

    account_type = serializers.ChoiceField(
        choices=AccountType.choices,
        required=False,
    )
    is_active = serializers.BooleanField(required=False)
