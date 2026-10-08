from django.core.exceptions import ValidationError
from django.db import models, transaction

from apps.accounting.enums import EntryStatus
from apps.accounting.models.journal_entry import JournalEntry


class JournalLineQuerySet(models.QuerySet):
    """
    Protege movimientos pertenecientes a asientos publicados.
    @version 1.0
    @author Agustin
    """

    def _lock_entries(self, entry_ids):
        """
        Bloquea los asientos padre por ID en orden estable y valida DRAFT.
        @version 1.0
        @author Agustin
        """
        entry_ids = set(entry_ids)
        entries = list(
            JournalEntry.objects.select_for_update()
            .filter(pk__in=entry_ids)
            .order_by("pk")
        )
        if len(entries) != len(set(entry_ids)) or any(
            entry.status != EntryStatus.DRAFT for entry in entries
        ):
            raise ValidationError("Los movimientos solo pueden operarse en asientos DRAFT.")
        return {entry.pk: entry for entry in entries}

    def update(self, **kwargs):
        """
        Rechaza cambios masivos en movimientos históricos.
        @version 1.2
        @author Agustin
        """
        with transaction.atomic():
            entry_ids = set(self.values_list("journal_entry_id", flat=True).distinct())
            target_entry = kwargs.get("journal_entry_id", kwargs.get("journal_entry"))
            if target_entry is not None:
                if hasattr(target_entry, "resolve_expression"):
                    if not isinstance(target_entry, models.Case):
                        raise ValidationError("El asiento destino debe identificarse antes del cambio.")
                    results = [case.result for case in target_entry.cases]
                    if target_entry.default is not None:
                        results.append(target_entry.default)
                    if any(not isinstance(result, models.Value) for result in results):
                        raise ValidationError("El asiento destino debe identificarse antes del cambio.")
                    entry_ids.update(result.value for result in results)
                else:
                    entry_ids.add(getattr(target_entry, "pk", target_entry))
            self._lock_entries(entry_ids)
            current_ids = set(self.values_list("journal_entry_id", flat=True).distinct())
            if not current_ids.issubset(entry_ids):
                raise ValidationError("Los movimientos cambiaron de asiento; vuelva a intentar.")
            return super().update(**kwargs)

    def delete(self):
        """
        Rechaza la eliminación masiva de movimientos históricos.
        @version 1.1
        @author Agustin
        """
        with transaction.atomic():
            entry_ids = set(self.values_list("journal_entry_id", flat=True).distinct())
            self._lock_entries(entry_ids)
            current_ids = set(self.values_list("journal_entry_id", flat=True).distinct())
            if not current_ids.issubset(entry_ids):
                raise ValidationError("Los movimientos cambiaron de asiento; vuelva a intentar.")
            return super().delete()

    def bulk_create(self, objs, **kwargs):
        """
        Rechaza la creación masiva dentro de asientos publicados.
        @version 1.1
        @author Agustin
        """
        objs = list(objs)
        with transaction.atomic():
            self._lock_entries(obj.journal_entry_id for obj in objs)
            return super().bulk_create(objs, **kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        """
        Bloquea todos los asientos antes de actualizar por lotes.
        @version 1.0
        @author Agustin
        """
        objs = list(objs)
        with transaction.atomic():
            line_ids = [obj.pk for obj in objs if obj.pk is not None]
            entry_ids = set(
                self.filter(pk__in=line_ids).values_list("journal_entry_id", flat=True)
            )
            if "journal_entry" in fields:
                entry_ids.update(obj.journal_entry_id for obj in objs)
            self._lock_entries(entry_ids)
            current_ids = set(
                self.filter(pk__in=line_ids).values_list("journal_entry_id", flat=True)
            )
            if not current_ids.issubset(entry_ids):
                raise ValidationError("Los movimientos cambiaron de asiento; vuelva a intentar.")
            return super().bulk_update(objs, fields, batch_size=batch_size)


class JournalLine(models.Model):
    """
    Representa un importe de Debe o Haber en un asiento.
    @version 1.1
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

    objects = JournalLineQuerySet.as_manager()

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
        Valida cuenta y asiento, permitiendo cuentas inactivas sólo en la reversión interna.
        @version 1.2
        @author Agustin
        """
        errors = {}
        if self.journal_entry_id and self.account_id:
            if self.journal_entry.status == EntryStatus.POSTED:
                errors["journal_entry"] = "No se pueden agregar movimientos a un asiento publicado."
            account = self.account
            if account.company_id != self.journal_entry.company_id:
                errors["account"] = "La cuenta debe pertenecer a la compañía del asiento."
            if not account.is_active and not getattr(self, "_allow_inactive_account", False):
                errors["account"] = "La cuenta debe estar activa al incorporar el movimiento."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """
        Valida las reglas contables antes de persistir el movimiento.
        @version 1.2
        @author Agustin
        """
        with transaction.atomic():
            entry_ids = {self.journal_entry_id}
            previous_entry_id = None
            if self.pk:
                previous_entry_id = type(self).objects.filter(pk=self.pk).values_list(
                    "journal_entry_id", flat=True
                ).first()
                if previous_entry_id is not None:
                    entry_ids.add(previous_entry_id)
            entries = type(self).objects.get_queryset()._lock_entries(entry_ids)
            if self.pk and previous_entry_id is not None:
                current_entry_id = type(self).objects.filter(pk=self.pk).values_list(
                    "journal_entry_id", flat=True
                ).first()
                if current_entry_id != previous_entry_id:
                    raise ValidationError("El movimiento cambió de asiento; vuelva a cargarlo.")
            self.journal_entry = entries[self.journal_entry_id]
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Impide eliminar movimientos de un asiento publicado.
        @version 1.1
        @author Agustin
        """
        with transaction.atomic():
            entry_id = type(self).objects.filter(pk=self.pk).values_list(
                "journal_entry_id", flat=True
            ).first()
            if entry_id is None:
                return super().delete(*args, **kwargs)
            type(self).objects.get_queryset()._lock_entries({entry_id})
            current_entry_id = type(self).objects.filter(pk=self.pk).values_list(
                "journal_entry_id", flat=True
            ).first()
            if current_entry_id is not None and current_entry_id != entry_id:
                raise ValidationError("El movimiento cambió de asiento; vuelva a cargarlo.")
            return super().delete(*args, **kwargs)
