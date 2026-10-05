import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.urls import include, path
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounting.enums import AccountType, EntryOrigin, EntryStatus
from apps.accounting.models import Account, JournalEntry, JournalLine
from apps.accounting.services import publish_journal_entry
from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


urlpatterns = [path("api/accounting/", include("apps.accounting.urls"))]


class JournalEntryPublicationTests(APITestCase):
    """Verifica publicación, inmutabilidad y origen de los asientos.

    @version 1.0
    @author Agustin
    """

    def setUp(self):
        """Prepara compañías y cuentas para los casos de publicación.

        @version 1.0
        @author Agustin
        """
        self.company = Company.objects.create(name="Primera")
        self.other_company = Company.objects.create(name="Segunda")
        self.debit_account = self.create_account(self.company, "1.1.01")
        self.credit_account = self.create_account(self.company, "2.1.01")
        self.other_account = self.create_account(self.other_company, "1.1.01")

    def create_account(self, company, code, is_active=True):
        """Crea una cuenta para los escenarios de publicación.

        @version 1.0
        @author Agustin
        """
        return Account.objects.create(
            company=company,
            code=code,
            name=f"Cuenta {code}",
            account_type=AccountType.ASSET,
            is_active=is_active,
        )

    def create_entry(self, company=None, **kwargs):
        """Crea un borrador en la compañía indicada.

        @version 1.0
        @author Agustin
        """
        return JournalEntry.objects.create(
            company=company or self.company,
            accounting_date=date(2026, 10, 5),
            description="Asiento de prueba",
            **kwargs,
        )

    def create_line(self, entry, account, debit="0.00", credit="0.00"):
        """Crea una línea con los importes indicados.

        @version 1.0
        @author Agustin
        """
        return JournalLine.objects.create(
            journal_entry=entry,
            account=account,
            description="Movimiento de prueba",
            debit=Decimal(debit),
            credit=Decimal(credit),
        )

    def make_publishable(self, entry=None):
        """Agrega dos líneas balanceadas al asiento y lo publica.

        @version 1.0
        @author Agustin
        """
        entry = entry or self.create_entry()
        debit = self.create_line(entry, self.debit_account, debit="25.00")
        credit = self.create_line(entry, self.credit_account, credit="25.00")
        return entry, debit, credit

    def test_balanced_draft_is_published(self):
        """Publica un borrador balanceado.

        @version 1.0
        @author Agustin
        """
        entry, _, _ = self.make_publishable()

        published = publish_journal_entry(entry.pk)

        self.assertEqual(published.status, EntryStatus.POSTED)

    def test_entry_with_fewer_than_two_lines_stays_draft(self):
        """Rechaza un asiento incompleto sin cambiar su estado.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry()
        self.create_line(entry, self.debit_account, debit="10.00")

        with self.assertRaises(ValidationError):
            publish_journal_entry(entry.pk)

        entry.refresh_from_db()
        self.assertEqual(entry.status, EntryStatus.DRAFT)

    def test_unbalanced_entry_stays_draft(self):
        """Rechaza un asiento desbalanceado sin cambiar su estado.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry()
        self.create_line(entry, self.debit_account, debit="10.00")
        self.create_line(entry, self.credit_account, credit="9.00")

        with self.assertRaises(ValidationError):
            publish_journal_entry(entry.pk)

        entry.refresh_from_db()
        self.assertEqual(entry.status, EntryStatus.DRAFT)

    def test_posted_entry_cannot_be_published_again(self):
        """Rechaza publicar por segunda vez un asiento histórico.

        @version 1.0
        @author Agustin
        """
        entry, _, _ = self.make_publishable()
        publish_journal_entry(entry.pk)

        with self.assertRaises(ValidationError):
            publish_journal_entry(entry.pk)

    def test_draft_cannot_be_posted_through_instance_save(self):
        """Exige que el cambio de estado pase por el service.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry()
        entry.status = EntryStatus.POSTED

        with self.assertRaises(ValidationError):
            entry.save()

    def test_inactive_account_prevents_publication(self):
        """Comprueba la actividad de la cuenta al momento de publicar.

        @version 1.0
        @author Agustin
        """
        entry, _, _ = self.make_publishable()
        self.debit_account.is_active = False
        self.debit_account.save(update_fields=("is_active",))

        with self.assertRaises(ValidationError):
            publish_journal_entry(entry.pk)

        entry.refresh_from_db()
        self.assertEqual(entry.status, EntryStatus.DRAFT)

    def test_account_from_another_company_prevents_publication(self):
        """Revalida la compañía de las cuentas antes de publicar.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry()
        JournalLine.objects.bulk_create(
            [
                JournalLine(
                    journal_entry=entry,
                    account=self.other_account,
                    description="Cuenta de otra compañía",
                    debit=Decimal("10.00"),
                )
            ]
        )
        self.create_line(entry, self.credit_account, credit="10.00")

        with self.assertRaises(ValidationError):
            publish_journal_entry(entry.pk)

        entry.refresh_from_db()
        self.assertEqual(entry.status, EntryStatus.DRAFT)

    def test_published_entry_rejects_instance_save(self):
        """Impide modificar un asiento publicado mediante save().

        @version 1.0
        @author Agustin
        """
        entry, _, _ = self.make_publishable()
        publish_journal_entry(entry.pk)
        entry.description = "Cambio"

        with self.assertRaises(ValidationError):
            entry.save()

        entry.refresh_from_db()
        self.assertEqual(entry.description, "Asiento de prueba")

    def test_published_entry_rejects_instance_delete(self):
        """Impide eliminar un asiento publicado mediante delete().

        @version 1.0
        @author Agustin
        """
        entry, _, _ = self.make_publishable()
        publish_journal_entry(entry.pk)

        with self.assertRaises(ValidationError):
            entry.delete()

        self.assertTrue(JournalEntry.objects.filter(pk=entry.pk).exists())

    def test_published_entry_rejects_queryset_update(self):
        """Impide modificar asientos publicados mediante update().

        @version 1.0
        @author Agustin
        """
        entry, _, _ = self.make_publishable()
        publish_journal_entry(entry.pk)

        with self.assertRaises(ValidationError):
            JournalEntry.objects.filter(pk=entry.pk).update(description="Cambio")

    def test_queryset_update_cannot_post_a_draft(self):
        """Exige publicar borradores mediante la operación de dominio.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry()

        with self.assertRaises(ValidationError):
            JournalEntry.objects.filter(pk=entry.pk).update(status=EntryStatus.POSTED)

    def test_published_entry_rejects_queryset_delete(self):
        """Impide eliminar asientos publicados mediante QuerySet.delete().

        @version 1.0
        @author Agustin
        """
        entry, _, _ = self.make_publishable()
        publish_journal_entry(entry.pk)

        with self.assertRaises(ValidationError):
            JournalEntry.objects.filter(pk=entry.pk).delete()

    def test_bulk_create_rejects_entries_without_save_numbering(self):
        """Rechaza la creación masiva para conservar la numeración correlativa.

        @version 1.0
        @author Agustin
        """
        entries = [
            JournalEntry(
                company=self.company,
                accounting_date=date(2026, 10, 5),
                description="Primer borrador",
            ),
            JournalEntry(
                company=self.company,
                accounting_date=date(2026, 10, 5),
                description="Segundo borrador",
            ),
        ]

        with self.assertRaises(ValidationError):
            JournalEntry.objects.bulk_create(entries)

        self.assertFalse(JournalEntry.objects.filter(company=self.company).exists())

    def test_duplicate_origin_in_same_company_is_rejected(self):
        """Aplica unicidad al mismo origen dentro de una compañía.

        @version 1.0
        @author Agustin
        """
        self.create_entry(source_type=EntryOrigin.IMPORT, source_id="file-1")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_entry(source_type=EntryOrigin.IMPORT, source_id="file-1")

    def test_same_origin_is_allowed_in_another_company(self):
        """Permite reutilizar un origen en compañías distintas.

        @version 1.0
        @author Agustin
        """
        self.create_entry(source_type=EntryOrigin.IMPORT, source_id="file-1")

        other_entry = self.create_entry(
            company=self.other_company,
            source_type=EntryOrigin.IMPORT,
            source_id="file-1",
        )

        self.assertEqual(other_entry.source_id, "file-1")

    def test_multiple_null_and_empty_source_ids_are_allowed(self):
        """Permite múltiples asientos manuales sin ID de origen.

        @version 1.0
        @author Agustin
        """
        entries = [
            self.create_entry(source_id=None),
            self.create_entry(source_id=None),
            self.create_entry(source_id=""),
            self.create_entry(source_id=""),
        ]

        self.assertEqual(len(entries), 4)

    def test_published_line_rejects_instance_save(self):
        """Impide modificar una línea publicada mediante save().

        @version 1.0
        @author Agustin
        """
        entry, debit, _ = self.make_publishable()
        publish_journal_entry(entry.pk)
        debit.description = "Cambio"

        with self.assertRaises(ValidationError):
            debit.save()

    def test_published_line_rejects_instance_delete(self):
        """Impide eliminar una línea publicada mediante delete().

        @version 1.0
        @author Agustin
        """
        entry, debit, _ = self.make_publishable()
        publish_journal_entry(entry.pk)

        with self.assertRaises(ValidationError):
            debit.delete()

    def test_published_line_rejects_new_line_using_stale_entry(self):
        """Consulta en DB el estado al agregar usando una instancia obsoleta.

        @version 1.0
        @author Agustin
        """
        entry, _, _ = self.make_publishable()
        publish_journal_entry(entry.pk)

        with self.assertRaises(ValidationError):
            self.create_line(entry, self.debit_account, debit="1.00")

    def test_published_line_rejects_queryset_update(self):
        """Impide cambiar una línea publicada mediante update().

        @version 1.0
        @author Agustin
        """
        entry, debit, _ = self.make_publishable()
        publish_journal_entry(entry.pk)

        with self.assertRaises(ValidationError):
            JournalLine.objects.filter(pk=debit.pk).update(description="Cambio")

    def test_published_line_rejects_bulk_update(self):
        """Verifica que bulk_update pase por la protección transaccional.

        @version 1.0
        @author Agustin
        """
        entry, debit, _ = self.make_publishable()
        publish_journal_entry(entry.pk)
        debit.description = "Cambio"

        with self.assertRaises(ValidationError):
            JournalLine.objects.bulk_update([debit], ["description"])

    def test_published_line_rejects_queryset_delete(self):
        """Impide eliminar líneas publicadas mediante QuerySet.delete().

        @version 1.0
        @author Agustin
        """
        entry, debit, _ = self.make_publishable()
        publish_journal_entry(entry.pk)

        with self.assertRaises(ValidationError):
            JournalLine.objects.filter(pk=debit.pk).delete()

    def test_published_line_rejects_bulk_create(self):
        """Impide agregar líneas mediante bulk_create() a un asiento publicado.

        @version 1.0
        @author Agustin
        """
        entry, _, _ = self.make_publishable()
        publish_journal_entry(entry.pk)
        line = JournalLine(
            journal_entry=entry,
            account=self.debit_account,
            description="Nueva línea",
            debit=Decimal("1.00"),
        )

        with self.assertRaises(ValidationError):
            JournalLine.objects.bulk_create([line])


@override_settings(ROOT_URLCONF=__name__)
class JournalEntryPublicationAccessTests(APITestCase):
    """Verifica membership y aislamiento del endpoint de publicación.

    @version 1.0
    @author Agustin
    """

    def setUp(self):
        """Prepara usuario y compañías con membership limitada.

        @version 1.0
        @author Agustin
        """
        self.user = User.objects.create(id=uuid.uuid4(), email="member@example.com")
        self.company = Company.objects.create(name="Primera")
        self.other_company = Company.objects.create(name="Segunda")
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=CompanyRole.objects.get(code="member"),
        )
        self.client.force_authenticate(user=self.user)

    def create_entry(self, company):
        """Crea un asiento dentro de la compañía indicada.

        @version 1.0
        @author Agustin
        """
        return JournalEntry.objects.create(
            company=company,
            accounting_date=date(2026, 10, 5),
            description="Asiento de prueba",
        )

    def publish_url(self, company, entry):
        """Devuelve la URL de publicación del asiento indicado.

        @version 1.0
        @author Agustin
        """
        return f"/api/accounting/companies/{company.pk}/journal-entries/{entry.pk}/publish/"

    def test_membership_is_required(self):
        """Rechaza al usuario autenticado que no pertenece a la compañía.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry(self.other_company)

        response = self.client.post(self.publish_url(self.other_company, entry))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_company_entry_is_not_found_through_authorized_company_url(self):
        """Aísla el asiento cuando la URL referencia otra compañía.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry(self.other_company)

        response = self.client.post(self.publish_url(self.company, entry))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
