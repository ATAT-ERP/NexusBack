import uuid
from datetime import date
from decimal import Decimal

from django.test import override_settings
from django.urls import include, path
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounting.enums import AccountType, EntryOrigin, EntryStatus
from apps.accounting.models import Account, JournalEntry, JournalLine
from apps.accounting.services import publish_journal_entry, reverse_journal_entry
from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


urlpatterns = [path("api/accounting/", include("apps.accounting.urls"))]


@override_settings(ROOT_URLCONF=__name__)
class AccountingQueryTests(APITestCase):
    """
    Verifica el Historial, el Libro Diario, el Libro Mayor y Sumas y Saldos.

    @version 1.0
    @author Agustin
    """

    def setUp(self):
        """
        Prepara la Company autorizada, su historial base y una Company ajena.

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

        self.caja = self.create_account(self.company, "1.1.01")
        self.banco = self.create_account(self.company, "1.1.02")
        self.otros = self.create_account(self.company, "5.1.01")
        self.ajena = self.create_account(self.other_company, "9.9.99")
        self.ajena_contrapartida = self.create_account(self.other_company, "9.9.98")

        # Caja +100 / Otros -100
        self.entry_1 = self.create_published_entry(
            date(2026, 1, 10), "Compra de insumos", self.caja, self.otros, "100.00"
        )
        # Otros +60 / Caja -60
        self.entry_2 = self.create_published_entry(
            date(2026, 2, 10), "Venta de mercadería", self.otros, self.caja, "60.00"
        )
        self.draft = self.create_entry(
            date(2026, 3, 5), "Asiento borrador", self.caja, self.otros, "999.00"
        )
        self.other_entry = self.create_published_entry(
            date(2026, 4, 5),
            "Asiento ajeno",
            self.ajena,
            self.ajena_contrapartida,
            "7.00",
            company=self.other_company,
        )

        self.history_url = (
            f"/api/accounting/companies/{self.company.pk}/journal-entries/"
        )
        self.diary_url = (
            f"/api/accounting/companies/{self.company.pk}/reports/daily-journal/"
        )
        self.trial_url = (
            f"/api/accounting/companies/{self.company.pk}/reports/trial-balance/"
        )
        self.other_history_url = (
            f"/api/accounting/companies/{self.other_company.pk}/journal-entries/"
        )

    def create_account(self, company, code):
        """
        Crea una cuenta activa en la compañía indicada.

        @version 1.0
        @author Agustin
        """
        return Account.objects.create(
            company=company,
            code=code,
            name=f"Cuenta {code}",
            account_type=AccountType.ASSET,
        )

    def create_entry(
        self,
        accounting_date,
        description,
        debit_account,
        credit_account,
        amount,
        company=None,
        **kwargs,
    ):
        """
        Crea un asiento borrador con dos movimientos balanceados.

        @version 1.0
        @author Agustin
        """
        entry = JournalEntry.objects.create(
            company=company or self.company,
            accounting_date=accounting_date,
            description=description,
            **kwargs,
        )
        JournalLine.objects.create(
            journal_entry=entry,
            account=debit_account,
            description=description,
            debit=Decimal(amount),
        )
        JournalLine.objects.create(
            journal_entry=entry,
            account=credit_account,
            description=description,
            credit=Decimal(amount),
        )
        return entry

    def create_published_entry(
        self,
        accounting_date,
        description,
        debit_account,
        credit_account,
        amount,
        company=None,
        **kwargs,
    ):
        """
        Crea y publica un asiento con dos movimientos balanceados.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry(
            accounting_date,
            description,
            debit_account,
            credit_account,
            amount,
            company=company,
            **kwargs,
        )
        return publish_journal_entry(entry.pk)

    def ledger_url(self, account):
        """
        Devuelve la URL del Libro Mayor para la cuenta indicada.

        @version 1.0
        @author Agustin
        """
        return (
            f"/api/accounting/companies/{self.company.pk}"
            f"/reports/general-ledger/{account.pk}/"
        )

    def test_history_lists_only_valid_entries_in_chronological_order(self):
        """
        Lista el historial sin borradores, ajenos ni fuera de orden.

        @version 1.0
        @author Agustin
        """
        response = self.client.get(self.history_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["number"] for item in response.data],
            [self.entry_1.number, self.entry_2.number],
        )

    def test_history_filters_by_date_range_status_and_source_type(self):
        """
        Aplica los filtros iniciales del historial de asientos.

        @version 1.0
        @author Agustin
        """
        imported = publish_journal_entry(
            self.create_entry(
                date(2026, 5, 5),
                "Importación",
                self.caja,
                self.otros,
                "10.00",
                source_type=EntryOrigin.IMPORT,
            ).pk
        )
        reverse_journal_entry(self.entry_1.pk, user=self.user)

        response = self.client.get(
            self.history_url,
            {
                "accounting_date_from": "2026-02-01",
                "accounting_date_to": "2026-04-30",
            },
        )
        self.assertEqual(
            [item["number"] for item in response.data], [self.entry_2.number]
        )

        response = self.client.get(self.history_url, {"status": EntryStatus.REVERSED})
        self.assertEqual(
            [item["number"] for item in response.data], [self.entry_1.number]
        )

        response = self.client.get(self.history_url, {"status": EntryStatus.DRAFT})
        self.assertEqual(response.data, [])

        response = self.client.get(
            self.history_url, {"source_type": EntryOrigin.IMPORT}
        )
        self.assertEqual([item["number"] for item in response.data], [imported.number])

    def test_history_rejects_invalid_filters(self):
        """
        Rechaza estados y fechas fuera del contrato de consulta.

        @version 1.0
        @author Agustin
        """
        response = self.client.get(self.history_url, {"status": "UNKNOWN"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.get(
            self.history_url, {"accounting_date_from": "no-es-fecha"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_history_detail_includes_lines_and_hides_invalid_entries(self):
        """
        Detalla los movimientos y oculta borradores y asientos ajenos.

        @version 1.0
        @author Agustin
        """
        response = self.client.get(f"{self.history_url}{self.entry_1.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["number"], self.entry_1.number)
        lines = response.data["lines"]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["account_code"], "1.1.01")
        self.assertEqual(lines[0]["account_name"], "Cuenta 1.1.01")
        self.assertEqual(Decimal(lines[0]["debit"]), Decimal("100.00"))
        self.assertEqual(Decimal(lines[1]["credit"]), Decimal("100.00"))

        response = self.client.get(f"{self.history_url}{self.draft.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        response = self.client.get(f"{self.history_url}{self.other_entry.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_all_queries_require_company_membership(self):
        """
        Rechaza al usuario autenticado sin membership en la Company.

        @version 1.0
        @author Agustin
        """
        base = f"/api/accounting/companies/{self.other_company.pk}"
        urls = [
            self.other_history_url,
            f"{self.other_history_url}{self.other_entry.pk}/",
            f"{base}/reports/daily-journal/",
            f"{base}/reports/trial-balance/",
            f"{base}/reports/general-ledger/{self.ajena.pk}/",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(
                    self.client.get(url).status_code, status.HTTP_403_FORBIDDEN
                )

    def test_all_queries_reject_unauthenticated_requests(self):
        """
        Exige autenticación en todas las consultas contables.

        @version 1.0
        @author Agustin
        """
        anonymous = APIClient()
        urls = [
            self.history_url,
            self.diary_url,
            self.trial_url,
            self.ledger_url(self.caja),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(
                    anonymous.get(url).status_code, status.HTTP_401_UNAUTHORIZED
                )

    def test_daily_journal_is_chronological_and_includes_lines(self):
        """
        Ordena el Libro Diario por fecha contable con sus movimientos.

        @version 1.0
        @author Agustin
        """
        response = self.client.get(self.diary_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["number"] for item in response.data],
            [self.entry_1.number, self.entry_2.number],
        )
        first = response.data[0]
        self.assertEqual(first["accounting_date"], "2026-01-10")
        self.assertEqual(first["description"], "Compra de insumos")
        self.assertEqual(
            [
                (line["account_code"], str(line["debit"]), str(line["credit"]))
                for line in first["lines"]
            ],
            [("1.1.01", "100.00", "0.00"), ("5.1.01", "0.00", "100.00")],
        )

    def test_daily_journal_filters_by_date_range_and_excludes_drafts(self):
        """
        Acota el Libro Diario al rango y descarta los borradores.

        @version 1.0
        @author Agustin
        """
        response = self.client.get(
            self.diary_url,
            {"accounting_date_from": "2026-02-01", "accounting_date_to": "2026-02-28"},
        )
        self.assertEqual(
            [item["number"] for item in response.data], [self.entry_2.number]
        )

        response = self.client.get(
            self.diary_url,
            {"accounting_date_from": "2026-03-01", "accounting_date_to": "2026-03-31"},
        )
        self.assertEqual(response.data, [])

    def test_daily_journal_keeps_reversals_for_economic_reconstruction(self):
        """
        Conserva el asiento revertido y su reversión en el historial.

        @version 1.0
        @author Agustin
        """
        reverse_journal_entry(self.entry_1.pk, user=self.user)
        reversal = JournalEntry.objects.get(reversal_of=self.entry_1)

        response = self.client.get(
            self.diary_url,
            {"accounting_date_from": "2026-01-01", "accounting_date_to": "2026-12-31"},
        )
        statuses = {item["number"]: item["status"] for item in response.data}
        self.assertEqual(statuses[self.entry_1.number], EntryStatus.REVERSED)
        self.assertEqual(statuses[reversal.number], EntryStatus.POSTED)

        ledger = self.client.get(self.ledger_url(self.caja))
        self.assertEqual(
            Decimal(ledger.data[-1]["balance"]), Decimal("-60.00")
        )

    def test_general_ledger_accumulates_balance(self):
        """
        Muestra cada movimiento de la cuenta con el saldo acumulado.

        @version 1.0
        @author Agustin
        """
        response = self.client.get(self.ledger_url(self.caja))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        first, second = response.data
        self.assertEqual(first["accounting_date"], "2026-01-10")
        self.assertEqual(first["entry_number"], self.entry_1.number)
        self.assertEqual(first["description"], "Compra de insumos")
        self.assertEqual(Decimal(first["debit"]), Decimal("100.00"))
        self.assertEqual(Decimal(first["credit"]), Decimal("0.00"))
        self.assertEqual(Decimal(first["balance"]), Decimal("100.00"))
        self.assertEqual(second["entry_number"], self.entry_2.number)
        self.assertEqual(Decimal(second["debit"]), Decimal("0.00"))
        self.assertEqual(Decimal(second["credit"]), Decimal("60.00"))
        self.assertEqual(Decimal(second["balance"]), Decimal("40.00"))

    def test_general_ledger_opens_with_the_prior_history(self):
        """
        Inicia el saldo con los movimientos anteriores al rango consultado.

        @version 1.0
        @author Agustin
        """
        response = self.client.get(
            self.ledger_url(self.caja), {"accounting_date_from": "2026-02-01"}
        )

        self.assertEqual(len(response.data), 1)
        row = response.data[0]
        self.assertEqual(row["entry_number"], self.entry_2.number)
        self.assertEqual(Decimal(row["credit"]), Decimal("60.00"))
        self.assertEqual(Decimal(row["balance"]), Decimal("40.00"))

    def test_general_ledger_excludes_drafts(self):
        """
        Descarta los movimientos de asientos borrador.

        @version 1.0
        @author Agustin
        """
        response = self.client.get(
            self.ledger_url(self.caja),
            {"accounting_date_from": "2026-03-01", "accounting_date_to": "2026-03-31"},
        )

        self.assertEqual(response.data, [])

    def test_general_ledger_rejects_account_of_another_company(self):
        """
        Exige que la cuenta consultada pertenezca a la Company autorizada.

        @version 1.0
        @author Agustin
        """
        response = self.client.get(self.ledger_url(self.ajena))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_trial_balance_groups_totals_by_account(self):
        """
        Resume Debe, Haber y balance por cuenta con movimiento en el rango.

        @version 1.0
        @author Agustin
        """
        response = self.client.get(self.trial_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = {row["code"]: row for row in response.data}
        self.assertEqual(set(rows), {"1.1.01", "5.1.01"})

        caja = rows["1.1.01"]
        self.assertEqual(caja["account"], self.caja.pk)
        self.assertEqual(caja["name"], "Cuenta 1.1.01")
        self.assertEqual(Decimal(caja["total_debit"]), Decimal("100.00"))
        self.assertEqual(Decimal(caja["total_credit"]), Decimal("60.00"))
        self.assertEqual(Decimal(caja["balance"]), Decimal("40.00"))

        otros = rows["5.1.01"]
        self.assertEqual(Decimal(otros["total_debit"]), Decimal("60.00"))
        self.assertEqual(Decimal(otros["total_credit"]), Decimal("100.00"))
        self.assertEqual(Decimal(otros["balance"]), Decimal("-40.00"))

    def test_trial_balance_filters_by_date_range(self):
        """
        Calcula los totales sólo con los movimientos del rango consultado.

        @version 1.0
        @author Agustin
        """
        response = self.client.get(
            self.trial_url,
            {"accounting_date_from": "2026-02-01", "accounting_date_to": "2026-02-28"},
        )
        rows = {row["code"]: row for row in response.data}

        self.assertEqual(set(rows), {"1.1.01", "5.1.01"})
        self.assertEqual(Decimal(rows["1.1.01"]["total_debit"]), Decimal("0.00"))
        self.assertEqual(Decimal(rows["1.1.01"]["total_credit"]), Decimal("60.00"))
        self.assertEqual(Decimal(rows["1.1.01"]["balance"]), Decimal("-60.00"))

    def test_trial_balance_excludes_drafts_and_other_companies(self):
        """
        Ignora borradores y cuentas de compañías sin membership.

        @version 1.0
        @author Agustin
        """
        response = self.client.get(
            self.trial_url,
            {"accounting_date_from": "2026-03-01", "accounting_date_to": "2026-12-31"},
        )
        self.assertEqual(response.data, [])

        response = self.client.get(self.trial_url)
        self.assertNotIn(
            self.ajena.pk, [row["account"] for row in response.data]
        )
