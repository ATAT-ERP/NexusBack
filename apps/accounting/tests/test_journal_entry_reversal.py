import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import override_settings
from django.urls import include, path
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounting.enums import AccountType, EntryOrigin, EntryStatus
from apps.accounting.models import Account, JournalEntry, JournalLine
from apps.accounting.services import publish_journal_entry, reverse_journal_entry
from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


urlpatterns = [path("api/accounting/", include("apps.accounting.urls"))]


class JournalEntryReversalTests(APITestCase):
    """Verifica la reversión de asientos históricos.

    @version 1.0
    @author Agustin
    """

    def setUp(self):
        """Prepara compañías y cuentas para los casos de reversión.

        @version 1.0
        @author Agustin
        """
        self.company = Company.objects.create(name="Primera")
        self.other_company = Company.objects.create(name="Segunda")
        self.debit_account = self.create_account(self.company, "1.1.01")
        self.credit_account = self.create_account(self.company, "2.1.01")

    def create_account(self, company, code, is_active=True):
        """Crea una cuenta para los escenarios de reversión.

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

    def post_entry(self):
        """Publica un asiento balanceado de prueba.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry()
        self.create_line(entry, self.debit_account, debit="100.00")
        self.create_line(entry, self.credit_account, credit="100.00")
        publish_journal_entry(entry.pk)
        entry.refresh_from_db()
        return entry

    def test_posted_entry_is_reversed_with_swapped_lines(self):
        """Invierte los movimientos del asiento original publicado.

        @version 1.0
        @author Agustin
        """
        entry = self.post_entry()

        reversal = reverse_journal_entry(entry.pk)

        self.assertEqual(reversal.status, EntryStatus.POSTED)
        self.assertEqual(reversal.company, entry.company)
        self.assertEqual(reversal.reversal_of, entry)
        lines = list(reversal.lines.order_by("pk"))
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].account, self.debit_account)
        self.assertEqual(lines[0].debit, Decimal("0.00"))
        self.assertEqual(lines[0].credit, Decimal("100.00"))
        self.assertEqual(lines[1].account, self.credit_account)
        self.assertEqual(lines[1].debit, Decimal("100.00"))
        self.assertEqual(lines[1].credit, Decimal("0.00"))

    def test_original_entry_becomes_reversed(self):
        """Marca el asiento original como REVERSED conservándolo.

        @version 1.0
        @author Agustin
        """
        entry = self.post_entry()

        reverse_journal_entry(entry.pk)

        entry.refresh_from_db()
        self.assertEqual(entry.status, EntryStatus.REVERSED)
        self.assertEqual(entry.lines.count(), 2)

    def test_draft_entry_cannot_be_reversed(self):
        """Rechaza revertir un borrador.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry()
        self.create_line(entry, self.debit_account, debit="100.00")
        self.create_line(entry, self.credit_account, credit="100.00")

        with self.assertRaises(ValidationError):
            reverse_journal_entry(entry.pk)

        entry.refresh_from_db()
        self.assertEqual(entry.status, EntryStatus.DRAFT)

    def test_reversed_entry_cannot_be_reversed_again(self):
        """Impide ejecutar múltiples reversiones sobre el mismo asiento.

        @version 1.0
        @author Agustin
        """
        entry = self.post_entry()
        reverse_journal_entry(entry.pk)

        with self.assertRaises(ValidationError):
            reverse_journal_entry(entry.pk)

        self.assertEqual(entry.reversals.count(), 1)

    def test_reversal_keeps_created_by(self):
        """Registra el usuario creador de la reversión.

        @version 1.0
        @author Agustin
        """
        user = User.objects.create(id=uuid.uuid4(), email="actor@example.com")
        entry = self.post_entry()

        reversal = reverse_journal_entry(entry.pk, user=user)

        self.assertEqual(reversal.created_by, user)


@override_settings(ROOT_URLCONF=__name__)
class JournalEntryReverseAccessTests(APITestCase):
    """Verifica membership y aislamiento del endpoint de reversión.

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

    def reverse_url(self, company, entry):
        """Devuelve la URL de reversión del asiento indicado.

        @version 1.0
        @author Agustin
        """
        return f"/api/accounting/companies/{company.pk}/journal-entries/{entry.pk}/reverse/"

    def test_membership_is_required(self):
        """Rechaza al usuario autenticado que no pertenece a la compañía.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry(self.other_company)

        response = self.client.post(self.reverse_url(self.other_company, entry))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_company_entry_is_not_found_through_authorized_company_url(self):
        """Aísla el asiento cuando la URL referencia otra compañía.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry(self.other_company)

        response = self.client.post(self.reverse_url(self.company, entry))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_draft_reversal_returns_validation_error(self):
        """Devuelve error de validación al intentar revertir un borrador.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry(self.company)

        response = self.client.post(self.reverse_url(self.company, entry))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
