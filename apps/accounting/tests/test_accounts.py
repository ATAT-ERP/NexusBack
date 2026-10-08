import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.urls import include, path
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounting.enums import AccountType, EntryStatus
from apps.accounting.models import Account, JournalEntry, JournalLine
from apps.accounting.services import publish_journal_entry, reverse_journal_entry
from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


urlpatterns = [path("api/accounting/", include("apps.accounting.urls"))]


@override_settings(ROOT_URLCONF=__name__)
class AccountTests(APITestCase):
    """
    Verifica el aislamiento y las operaciones del plan de cuentas.

    @version 1.0
    @author Agustin
    """

    def setUp(self):
        """
        Prepara dos Companies y un usuario miembro de una sola.

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
        self.list_url = f"/api/accounting/companies/{self.company.pk}/accounts/"

    def test_create_requires_fields_and_account_type_choice(self):
        """
        Rechaza los campos obligatorios ausentes y tipos no declarados.

        @version 1.0
        @author Agustin
        """
        response = self.client.post(self.list_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(set(response.data), {"code", "name", "account_type"})
        self.assertIn("code", response.data)
        self.assertIn("name", response.data)
        self.assertIn("account_type", response.data)

        response = self.client.post(
            self.list_url,
            {"code": "1.1.01", "name": "Caja", "account_type": "UNKNOWN"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("account_type", response.data)

    def test_unauthenticated_requests_are_rejected(self):
        """
        Exige autenticación para consultar y crear cuentas.

        @version 1.0
        @author Agustin
        """
        anonymous_client = APIClient()
        response = anonymous_client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(set(response.data), {"detail"})
        self.assertEqual(
            anonymous_client.post(
                self.list_url,
                {"code": "1.1.01", "name": "Caja", "account_type": AccountType.ASSET},
                format="json",
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_create_scopes_company_and_rejects_duplicate_code(self):
        """
        Asigna la Company de la URL y evita códigos repetidos en ella.

        @version 1.1
        @author Agustin
        """
        payload = {
            "company": str(self.other_company.pk),
            "code": "1.1.01",
            "name": "Caja",
            "account_type": AccountType.ASSET,
        }
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Account.objects.get(pk=response.data["id"]).company, self.company)

        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"code": "NEX-ACC-001"})

    def test_database_duplicate_returns_only_the_functional_code(self):
        """Traduce una colisión posterior a validar sin dejar rota la transacción.

        @version 1.0
        @author Agustin
        """
        existing = self.create_account()
        payload = {"code": existing.code, "name": "Caja", "account_type": AccountType.ASSET}
        expected = {"code": "NEX-ACC-001"}
        self.assertEqual(self.client.post(self.list_url, payload, format="json").data, expected)
        account = self.create_account(code="1.1.02")
        with patch(
            "apps.accounting.serializers.account.AccountSerializer.validate_code",
            side_effect=lambda value: value,
        ):
            for method, url, data in (
                (self.client.post, self.list_url, payload),
                (self.client.patch, f"{self.list_url}{account.pk}/", {"code": existing.code}),
            ):
                with self.subTest(method=method.__name__):
                    response = method(url, data, format="json")
                    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                    self.assertEqual(response.data, expected)
                    self.assertEqual(Account.objects.filter(company=self.company).count(), 2)
        account.refresh_from_db()
        self.assertEqual(account.code, "1.1.02")

    def test_postgresql_duplicate_constraint_returns_the_same_error(self):
        """Verifica el diagnóstico PostgreSQL simulado, sin probar concurrencia.

        @version 1.0
        @author Agustin
        """
        cause = Exception("duplicate key")
        cause.diag = SimpleNamespace(constraint_name="unique_account_company_code")
        error = IntegrityError("duplicate key")
        error.__cause__ = cause
        payload = {"code": "1.1.01", "name": "Caja", "account_type": AccountType.ASSET}
        with patch(
            "apps.accounting.serializers.account.AccountSerializer.create", side_effect=error
        ):
            response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"code": "NEX-ACC-001"})
        self.assertEqual(Account.objects.count(), 0)

    def test_unrelated_integrity_errors_are_not_translated(self):
        """Mantiene visibles los fallos de integridad ajenos al código de cuenta.

        @version 1.0
        @author Agustin
        """
        for cause in (
            Exception("NOT NULL constraint failed: accounting_accounts.name"),
            Exception("UNIQUE constraint failed: accounting_accounts.id"),
            Exception("other constraint"),
        ):
            cause.diag = SimpleNamespace(constraint_name="other_constraint")
            error = IntegrityError(str(cause))
            error.__cause__ = cause
            with self.subTest(cause=str(cause)), patch(
                "apps.accounting.serializers.account.AccountSerializer.create",
                side_effect=error,
            ):
                with self.assertRaises(IntegrityError):
                    self.client.post(
                        self.list_url,
                        {"code": "1.1.01", "name": "Caja", "account_type": AccountType.ASSET},
                        format="json",
                    )
            self.assertEqual(Account.objects.count(), 0)

    def test_duplicate_returns_only_its_functional_code(self):
        """El código funcional no expone detalles de validación al cliente.

        @version 1.0
        @author Agustin
        """
        account = self.create_account()
        response = self.client.post(self.list_url, {"code": account.code}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"code": "NEX-ACC-001"})

    def test_same_code_is_allowed_for_different_companies(self):
        """
        La unicidad aplica a la pareja Company y código.

        @version 1.0
        @author Agustin
        """
        Account.objects.create(
            company=self.company,
            code="1.1.01",
            name="Caja",
            account_type=AccountType.ASSET,
        )
        Account.objects.create(
            company=self.other_company,
            code="1.1.01",
            name="Caja",
            account_type=AccountType.ASSET,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Account.objects.create(
                    company=self.company,
                    code="1.1.01",
                    name="Duplicada",
                    account_type=AccountType.ASSET,
                )

    def test_list_filters_and_excludes_other_company(self):
        """
        Lista solo las cuentas propias que cumplen los filtros.

        @version 1.0
        @author Agustin
        """
        active = Account.objects.create(
            company=self.company,
            code="1.1.01",
            name="Caja",
            account_type=AccountType.ASSET,
        )
        inactive = Account.objects.create(
            company=self.company,
            code="5.1.01",
            name="Gastos",
            account_type=AccountType.EXPENSE,
            is_active=False,
        )
        Account.objects.create(
            company=self.other_company,
            code="1.1.02",
            name="Banco",
            account_type=AccountType.ASSET,
        )
        response = self.client.get(
            self.list_url,
            {"account_type": AccountType.ASSET, "is_active": "true"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [active.pk])

        response = self.client.get(self.list_url, {"is_active": "false"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [inactive.pk])

    def test_detail_updates_and_deactivates_without_delete(self):
        """
        Permite editar y desactivar, pero no expone DELETE.

        @version 1.0
        @author Agustin
        """
        account = Account.objects.create(
            company=self.company,
            code="1.1.01",
            name="Caja",
            account_type=AccountType.ASSET,
        )
        url = f"{self.list_url}{account.pk}/"
        response = self.client.patch(
            url, {"name": "Caja general", "is_active": False}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        account.refresh_from_db()
        self.assertEqual(account.name, "Caja general")
        self.assertFalse(account.is_active)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_membership_is_required_for_every_operation(self):
        """
        Impide operar sobre cuentas de una Company ajena.

        @version 1.0
        @author Agustin
        """
        account = Account.objects.create(
            company=self.other_company,
            code="1.1.01",
            name="Caja",
            account_type=AccountType.ASSET,
        )
        other_url = f"/api/accounting/companies/{self.other_company.pk}/accounts/"
        payload = {"code": "2.1.01", "name": "Deuda", "account_type": AccountType.LIABILITY}
        response = self.client.get(other_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(set(response.data), {"detail"})
        self.assertEqual(
            self.client.post(other_url, payload, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        detail_url = f"{other_url}{account.pk}/"
        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.patch(detail_url, {"name": "Ajena"}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        response = self.client.get(f"{self.list_url}{account.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(set(response.data), {"detail"})

    def test_patch_cannot_update_another_company_account_by_id(self):
        """
        Rechaza un ID ajeno aunque la URL use una Company autorizada.

        @version 1.0
        @author Agustin
        """
        account = Account.objects.create(
            company=self.other_company,
            code="1.1.01",
            name="Caja ajena",
            account_type=AccountType.ASSET,
        )
        response = self.client.patch(
            f"{self.list_url}{account.pk}/",
            {"name": "Nombre cambiado"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        account.refresh_from_db()
        self.assertEqual(account.name, "Caja ajena")

    def test_patch_ignores_company_from_body(self):
        """
        Impide trasladar una cuenta enviando otra Company en el body.

        @version 1.0
        @author Agustin
        """
        account = Account.objects.create(
            company=self.company,
            code="1.1.01",
            name="Caja",
            account_type=AccountType.ASSET,
        )
        response = self.client.patch(
            f"{self.list_url}{account.pk}/",
            {"company": str(self.other_company.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        account.refresh_from_db()
        self.assertEqual(account.company, self.company)

    def test_patch_rejects_duplicate_code_in_company(self):
        """
        Rechaza cambiar el código por otro ya usado en la Company.

        @version 1.1
        @author Agustin
        """
        Account.objects.create(
            company=self.company,
            code="1.1.01",
            name="Caja",
            account_type=AccountType.ASSET,
        )
        account = Account.objects.create(
            company=self.company,
            code="1.1.02",
            name="Banco",
            account_type=AccountType.ASSET,
        )
        response = self.client.patch(
            f"{self.list_url}{account.pk}/",
            {"code": "1.1.01"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"code": "NEX-ACC-001"})
        account.refresh_from_db()
        self.assertEqual(account.code, "1.1.02")

    def create_account(self, code="1.1.01"):
        """Crea una cuenta del plan de la Company de prueba.

        @version 1.0
        @author Agustin
        """
        return Account.objects.create(
            company=self.company,
            code=code,
            name="Caja",
            account_type=AccountType.ASSET,
        )

    def create_posted_entry(self, account):
        """Publica un asiento balanceado que utiliza la cuenta indicada.

        @version 1.0
        @author Agustin
        """
        offset = self.create_account(code="9.9.99")
        entry = JournalEntry.objects.create(
            company=self.company,
            accounting_date=date(2026, 10, 8),
            description="Asiento histórico",
        )
        JournalLine.objects.create(
            journal_entry=entry,
            account=account,
            description="Debe",
            debit=Decimal("10.00"),
        )
        JournalLine.objects.create(
            journal_entry=entry,
            account=offset,
            description="Haber",
            credit=Decimal("10.00"),
        )
        publish_journal_entry(entry.pk)
        return entry

    def test_account_without_history_remains_editable(self):
        """Permite editar todos los datos de una cuenta sin movimientos.

        @version 1.0
        @author Agustin
        """
        account = self.create_account()
        account.code = "1.1.02"
        account.name = "Caja general"
        account.account_type = AccountType.LIABILITY
        account.is_active = False
        account.save()
        account.refresh_from_db()
        self.assertEqual(account.code, "1.1.02")
        self.assertEqual(account.name, "Caja general")
        self.assertEqual(account.account_type, AccountType.LIABILITY)
        self.assertFalse(account.is_active)

    def test_account_used_only_in_draft_remains_editable(self):
        """Permite editar una cuenta referenciada sólo por un borrador.

        @version 1.0
        @author Agustin
        """
        account = self.create_account()
        draft = JournalEntry.objects.create(
            company=self.company,
            accounting_date=date(2026, 10, 8),
            description="Borrador",
        )
        JournalLine.objects.create(
            journal_entry=draft,
            account=account,
            description="Debe",
            debit=Decimal("10.00"),
        )

        for code, name, account_type in (
            ("1.1.02", "Caja general", AccountType.LIABILITY),
            ("1.1.03", "Caja central", AccountType.EQUITY),
        ):
            account.code = code
            account.name = name
            account.account_type = account_type
            account.is_active = False
            account.save()
        account.refresh_from_db()
        self.assertEqual(account.code, "1.1.03")
        self.assertEqual(account.name, "Caja central")
        self.assertEqual(account.account_type, AccountType.EQUITY)
        self.assertFalse(account.is_active)
        self.assertEqual(draft.status, EntryStatus.DRAFT)

    def test_historical_account_protects_identity_but_allows_noop_and_deactivation(self):
        """Congela código, nombre y tipo tras publicar, pero admite actividad.

        @version 1.0
        @author Agustin
        """
        account = self.create_account()
        self.create_posted_entry(account)
        original = (account.code, account.name, account.account_type)

        for field, value in (
            ("code", "1.1.02"),
            ("name", "Caja modificada"),
            ("account_type", AccountType.LIABILITY),
        ):
            with self.subTest(field=field):
                setattr(account, field, value)
                with self.assertRaises(ValidationError):
                    account.save()
                account.refresh_from_db()
                self.assertEqual(
                    (account.code, account.name, account.account_type), original
                )

        account.save()
        account.name = "Cambio que no se guarda"
        account.is_active = False
        account.save(update_fields=["is_active"])
        account.refresh_from_db()
        self.assertFalse(account.is_active)
        self.assertEqual(account.name, "Caja")

    def test_reversed_entry_also_protects_account_identity(self):
        """Incluye REVERSED entre los estados que conservan identidad histórica.

        @version 1.0
        @author Agustin
        """
        account = self.create_account()
        entry = self.create_posted_entry(account)
        reverse_journal_entry(entry.pk)
        account.name = "Nombre nuevo"

        with self.assertRaises(ValidationError):
            account.save()

        account.refresh_from_db()
        self.assertEqual(account.name, "Caja")

    def test_queryset_update_rejects_historical_changes_but_allows_is_active(self):
        """Protege campos históricos en update() y permite desactivar.

        @version 1.0
        @author Agustin
        """
        account = self.create_account()
        self.create_posted_entry(account)

        with self.assertRaises(ValidationError):
            Account.objects.filter(pk=account.pk).update(name="Caja nueva")
        self.assertEqual(
            Account.objects.filter(pk=account.pk).update(is_active=False), 1
        )
        account.refresh_from_db()
        self.assertEqual(account.name, "Caja")
        self.assertFalse(account.is_active)

    def test_bulk_update_uses_historical_protection_and_allows_is_active(self):
        """Reutiliza update() para bloquear bulk_update() sin bloquear actividad.

        @version 1.0
        @author Agustin
        """
        account = self.create_account()
        self.create_posted_entry(account)
        account.name = "Caja nueva"

        with self.assertRaises(ValidationError):
            with transaction.atomic():
                Account.objects.bulk_update([account], ["name"])

        account.refresh_from_db()
        account.is_active = False
        Account.objects.bulk_update([account], ["is_active"])
        account.refresh_from_db()
        self.assertEqual(account.name, "Caja")
        self.assertFalse(account.is_active)

    def test_mixed_queryset_update_is_atomic_when_one_account_is_historical(self):
        """No modifica tampoco cuentas nuevas si el queryset incluye una histórica.

        @version 1.0
        @author Agustin
        """
        historical = self.create_account()
        current = self.create_account(code="1.1.02")
        self.create_posted_entry(historical)

        with self.assertRaises(ValidationError):
            Account.objects.filter(pk__in=[historical.pk, current.pk]).update(
                name="Cambio masivo"
            )

        historical.refresh_from_db()
        current.refresh_from_db()
        self.assertEqual(historical.name, "Caja")
        self.assertEqual(current.name, "Caja")

        current.name = "Cambio masivo"
        historical.name = "Cambio masivo"
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                Account.objects.bulk_update(
                    [current, historical], ["name"], batch_size=1
                )

        historical.refresh_from_db()
        current.refresh_from_db()
        self.assertEqual(historical.name, "Caja")
        self.assertEqual(current.name, "Caja")

    def test_api_rejects_historical_identity_change_and_allows_deactivation(self):
        """Devuelve 400 por cambios históricos y permite is_active por API.

        @version 1.1
        @author Agustin
        """
        account = self.create_account()
        self.create_posted_entry(account)
        url = f"{self.list_url}{account.pk}/"

        response = self.client.patch(url, {"name": "Caja nueva"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"code": "NEX-ACC-002"})

        response = self.client.patch(url, {"is_active": False}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
