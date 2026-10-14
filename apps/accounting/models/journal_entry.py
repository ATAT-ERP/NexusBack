from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Max

from apps.accounting.enums import Currency, EntryOrigin, EntryStatus
from apps.company.models import Company


class JournalEntryQuerySet(models.QuerySet):
    """
    Protege asientos publicados frente a operaciones masivas del ORM.
    @version 1.0
    @author Agustin
    """

    def update(self, **kwargs):
        """
        Actualiza borradores sin alterar su numeración ni Company.
        @version 1.2
        @author Agustin
        """
        if "status" in kwargs:
            raise ValidationError("El estado del asiento solo puede cambiarse mediante Accounting.")
        if {"number", "company", "company_id"}.intersection(kwargs):
            raise ValidationError("El número y la compañía del asiento no pueden modificarse.")
        with transaction.atomic():
            entries = list(self.select_for_update().order_by("pk"))
            if any(entry.status != EntryStatus.DRAFT for entry in entries):
                raise ValidationError("Solo se pueden modificar asientos en estado DRAFT.")
            return super().update(**kwargs)

    def delete(self):
        """
        Elimina asientos borrador después de bloquearlos en orden estable.
        @version 1.1
        @author Agustin
        """
        with transaction.atomic():
            entries = list(self.select_for_update().order_by("pk"))
            if any(entry.status != EntryStatus.DRAFT for entry in entries):
                raise ValidationError("Solo se pueden eliminar asientos en estado DRAFT.")
            return super().delete()

    def bulk_create(self, objs, **kwargs):
        """
        Rechaza la creación masiva para conservar la numeración de save().
        @version 1.1
        @author Agustin
        """
        objs = list(objs)
        if objs:
            raise ValidationError("No se admite crear asientos masivamente; use save().")
        return super().bulk_create(objs, **kwargs)


class JournalEntry(models.Model):
    """
    Representa un hecho contable registrado para una Company.
    @version 1.1
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

    objects = JournalEntryQuerySet.as_manager()

    class Meta:
        db_table = "accounting_journal_entries"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "number"],
                name="unique_journal_entry_company_number",
            ),
            models.UniqueConstraint(
                fields=["company", "source_type", "source_id"],
                condition=models.Q(source_id__isnull=False) & ~models.Q(source_id=""),
                name="unique_journal_entry_source",
            ),
        ]

    def save(self, *args, **kwargs):
        """
        Numera borradores al crearlos y conserva su número y Company al editarlos.
        @version 2.2
        @author Agustin
        """
        if self._state.adding:
            if self.status != EntryStatus.DRAFT:
                raise ValidationError("Los asientos deben crearse como borradores.")
            with transaction.atomic():
                Company.objects.select_for_update().get(pk=self.company_id)
                last_number = type(self).objects.filter(
                    company_id=self.company_id
                ).aggregate(Max("number"))["number__max"]
                self.number = (last_number or 0) + 1
                kwargs["force_insert"] = True
                return super().save(*args, **kwargs)
        with transaction.atomic():
            current = type(self).objects.select_for_update().get(pk=self.pk)
            if current.status != EntryStatus.DRAFT:
                raise ValidationError("Los asientos publicados no pueden modificarse.")
            if self.status != EntryStatus.DRAFT:
                raise ValidationError("Use la operación de publicación de Accounting.")
            if self.number != current.number or self.company_id != current.company_id:
                raise ValidationError("El número y la compañía del asiento no pueden modificarse.")
            return super().save(*args, **kwargs)

    def _mark_posted(self):
        """
        Persiste POSTED tras la validación y bloqueo del service de Accounting.
        @version 1.0
        @author Agustin
        """
        self.status = EntryStatus.POSTED
        return super().save(update_fields=("status", "updated_at"))

    def _mark_reversed(self):
        """
        Persiste REVERSED tras la validación y bloqueo del service de Accounting.
        @version 1.0
        @author Agustin
        """
        self.status = EntryStatus.REVERSED
        return super().save(update_fields=("status", "updated_at"))

    def delete(self, *args, **kwargs):
        """
        Elimina el asiento solo si sigue siendo borrador bajo bloqueo.
        @version 1.1
        @author Agustin
        """
        with transaction.atomic():
            current = type(self).objects.select_for_update().get(pk=self.pk)
            if current.status != EntryStatus.DRAFT:
                raise ValidationError("Los asientos publicados no pueden eliminarse.")
            return super().delete(*args, **kwargs)
