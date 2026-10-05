from django.db import models

from apps.accounting.enums import AccountType


class Account(models.Model):
    """
    Representa una cuenta del plan contable de una Company.

    @version 1.0
    @author Agustin
    """

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.PROTECT,
        related_name="accounts",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=16, choices=AccountType.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounting_accounts"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_account_company_code",
            ),
        ]
