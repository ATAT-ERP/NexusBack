from rest_framework import serializers

from apps.billing.models import FiscalProfile


class FiscalProfileSerializer(serializers.ModelSerializer):
    """
    Valida y expone la configuración fiscal sin editar datos de Company.
    @version 1.0
    @author Agustin
    """

    class Meta:
        model = FiscalProfile
        fields = (
            "company",
            "vat_condition",
            "gross_income",
            "business_start_date",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("company", "created_at", "updated_at")

    def validate(self, attrs):
        """
        Evita registrar más de un perfil fiscal para la Company indicada.
        @version 1.0
        @author Agustin
        """
        company = self.context.get("company")
        if (
            self.instance is None
            and company is not None
            and FiscalProfile.objects.filter(company=company).exists()
        ):
            raise serializers.ValidationError(
                {"company": "La compañía ya tiene un perfil fiscal."}
            )
        return attrs