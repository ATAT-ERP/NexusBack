from django.core.exceptions import ValidationError
from django.db import models


class JournalLine(models.Model):
    """
    Representa un importe de Debe o Haber en un asiento.
    @version 1.0
    @author Agustin
    """

    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )
    description = models.TextField()
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        db_table = "accounting_journal_lines"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(debit__gt=0, credit=0)
                    | models.Q(debit=0, credit__gt=0)
                ),
                name="journal_line_debit_or_credit",
            ),
        ]

    def clean(self):
        """
        Valida el importe y la relación entre cuenta y asiento.
        @version 1.0
        @author Agustin
        """
        errors = {}
        if self.journal_entry_id and self.account_id:
            account = self.account
            if account.company_id != self.journal_entry.company_id:
                errors["account"] = "La cuenta debe pertenecer a la compañía del asiento."
            if not account.is_active:
                errors["account"] = "La cuenta debe estar activa al incorporar el movimiento."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """
        Valida las reglas contables antes de persistir el movimiento.
        @version 1.0
        @author Agustin
        """
        self.full_clean()
        return super().save(*args, **kwargs)
