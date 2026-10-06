from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounting.enums import EntryStatus
from apps.accounting.models import Account, JournalEntry, JournalLine
from apps.company.models import Company


@transaction.atomic
def publish_journal_entry(entry_id):
    """
    Valida y publica un asiento como registro histórico inmutable.
    @version 1.1
    @author Agustin
    """
    entry = JournalEntry.objects.select_for_update().get(pk=entry_id)
    if entry.status != EntryStatus.DRAFT:
        raise ValidationError("Solo se pueden publicar asientos en estado DRAFT.")

    errors = []
    company = Company.objects.select_for_update().filter(pk=entry.company_id).first()
    if company is None:
        errors.append("El asiento debe pertenecer a una compañía válida.")

    lines = JournalLine.objects.filter(journal_entry=entry)
    if lines.count() < 2:
        errors.append("El asiento debe contener al menos dos movimientos.")
    account_ids = list(
        lines.values_list("account_id", flat=True).distinct().order_by("account_id")
    )
    accounts = list(
        Account.objects.select_for_update().filter(pk__in=account_ids).order_by("pk")
    )
    if any(account.company_id != entry.company_id for account in accounts):
        errors.append("Todas las cuentas deben pertenecer a la compañía del asiento.")
    if any(not account.is_active for account in accounts):
        errors.append("Todas las cuentas utilizadas deben estar activas.")

    totals = lines.aggregate(debit=Sum("debit"), credit=Sum("credit"))
    if totals["debit"] != totals["credit"]:
        errors.append("La suma del Debe debe ser igual a la suma del Haber.")

    if errors:
        raise ValidationError(errors)

    entry._mark_posted()
    return entry


@transaction.atomic
def reverse_journal_entry(entry_id, user=None):
    """
    Crea y publica el asiento inverso de un asiento histórico POSTED.
    @version 1.0
    @author Agustin
    """
    entry = JournalEntry.objects.select_for_update().get(pk=entry_id)
    if entry.status != EntryStatus.POSTED:
        raise ValidationError("Solo se pueden revertir asientos en estado POSTED.")

    reversal = JournalEntry(
        company=entry.company,
        accounting_date=timezone.localdate(),
        description=f"Reversión del asiento #{entry.number}: {entry.description}",
        source_type=entry.source_type,
        currency=entry.currency,
        created_by=user,
        reversal_of=entry,
    )
    reversal.save()
    for line in entry.lines.all():
        JournalLine.objects.create(
            journal_entry=reversal,
            account=line.account,
            description=line.description,
            debit=line.credit,
            credit=line.debit,
        )

    reversal = publish_journal_entry(reversal.pk)
    entry._mark_reversed()
    return reversal
