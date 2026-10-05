from django.db import models, transaction
from django.db.models import Max

from apps.accounting.enums import Currency, EntryOrigin, EntryStatus
from apps.company.models import Company


class JournalEntry(models.Model):
    """
    Representa un hecho contable registrado para una Company.
    @version 1.0
    @author Agustin
    """

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.PROTECT,
        related_name="journal_entries",
    )
    number = models.PositiveIntegerField(editable=False)
    accounting_date = models.DateField()
    description = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=EntryStatus.choices,
        default=EntryStatus.DRAFT,
    )
    source_type = models.CharField(
        max_length=16,
        choices=EntryOrigin.choices,
        default=EntryOrigin.MANUAL,
    )
    source_id = models.TextField(blank=True, null=True)
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.ARS,
    )
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="created_journal_entries",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reversal_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="reversals",
        blank=True,
        null=True,
    )
    metadata = models.JSONField(blank=True, null=True)

    class Meta:
        db_table = "accounting_journal_entries"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "number"],
                name="unique_journal_entry_company_number",
            ),
        ]

    def save(self, *args, **kwargs):
        """
        Asigna el siguiente número correlativo al crear el asiento.
        @version 1.0
        @author Agustin
        """
        if self._state.adding:
            with transaction.atomic():
                Company.objects.select_for_update().get(pk=self.company_id)
                last_number = type(self).objects.filter(
                    company_id=self.company_id
                ).aggregate(Max("number"))["number__max"]
                self.number = (last_number or 0) + 1
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)
