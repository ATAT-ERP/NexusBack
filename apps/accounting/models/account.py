from django.core.exceptions import ValidationError
from django.db import models, transaction

from apps.accounting.enums import AccountType, EntryStatus

PROTECTED_FIELDS = {"code", "name", "account_type"}
HISTORICAL_STATUSES = (EntryStatus.POSTED, EntryStatus.REVERSED)


class AccountQuerySet(models.QuerySet):
    """
    Protege la identificación de cuentas utilizadas en el historial.

    @version 1.0
    @author Agustin
    """

    def update(self, **kwargs):
        """
        Rechaza cambios masivos de cuentas con movimientos históricos.

        @version 1.0
        @author Agustin
        """
        if not PROTECTED_FIELDS.intersection(kwargs):
            return super().update(**kwargs)

        with transaction.atomic():
            account_ids = list(
                self.select_for_update().order_by("pk").values_list("pk", flat=True)
            )
            has_history = self.model.objects.filter(
                pk__in=account_ids,
                journal_lines__journal_entry__status__in=HISTORICAL_STATUSES,
            ).exists()
            if has_history:
                raise ValidationError(
                    "No se pueden cambiar código, nombre o tipo de una cuenta con movimientos históricos."
                )
            return super().update(**kwargs)


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

    objects = AccountQuerySet.as_manager()

    def save(self, *args, **kwargs):
        """
        Conserva los datos identificatorios de cuentas con historial publicado.

        @version 1.0
        @author Agustin
        """
        if self._state.adding:
            return super().save(*args, **kwargs)

        with transaction.atomic():
            current = type(self).objects.select_for_update().get(pk=self.pk)
            update_fields = kwargs.get("update_fields")
            fields = PROTECTED_FIELDS
            if update_fields is not None:
                fields = fields.intersection(update_fields)
            changed = any(
                getattr(self, field) != getattr(current, field) for field in fields
            )
            has_history = changed and type(self).objects.filter(
                pk=self.pk,
                journal_lines__journal_entry__status__in=HISTORICAL_STATUSES,
            ).exists()
            if has_history:
                raise ValidationError(
                    "No se pueden cambiar código, nombre o tipo de una cuenta con movimientos históricos."
                )
            return super().save(*args, **kwargs)
