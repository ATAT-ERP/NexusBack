from django.db import models

from apps.billing.enums import VATCondition


class FiscalProfile(models.Model):
    """
    Configuración fiscal de facturación asociada de forma única a una Company.
    @version 1.0
    @author Agustin
    """

    company = models.OneToOneField(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="fiscal_profile",
    )
    vat_condition = models.PositiveSmallIntegerField(
        choices=VATCondition.choices
    )
    gross_income = models.CharField(max_length=30, blank=True)
    business_start_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "billing_fiscal_profiles"

    def __str__(self):
        return f"FiscalProfile({self.company_id})"