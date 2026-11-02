import uuid
from copy import deepcopy
from decimal import Decimal

from django.test import override_settings
from django.urls import include, path
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounting.enums import AccountType, Currency, EntryOrigin, EntryStatus
from apps.accounting.models import Account, JournalEntry, JournalLine
from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


urlpatterns = [path("api/accounting/", include("apps.accounting.urls"))]


@override_settings(ROOT_URLCONF=__name__)
class ManualJournalEntryTests(APITestCase):
    """Verifica el circuito API de alta, recuperación y publicación manual.

    @version 1.0
    """

    def setUp(self):
        """Prepara un miembro y cuentas de dos compañías aisladas.

        @version 1.0
        """
        self.user = User.objects.create(id=uuid.uuid4(), email="accountant@example.com")
        self.company = Company.objects.create(name="Primera")
        self.other_company = Company.objects.create(name="Segunda")
        CompanyMember.objects.create(
            user=self.user, company=self.company,
            role=CompanyRole.objects.get(code="member"),
        )
        self.client.force_authenticate(user=self.user)
        self.cash = Account.objects.create(
            company=self.company, code="1.1", name="Caja", account_type=AccountType.ASSET,
        )
        self.capital = Account.objects.create(
            company=self.company, code="3.1", name="Capital", account_type=AccountType.EQUITY,
        )
        self.foreign = Account.objects.create(
            company=self.other_company, code="1.1", name="Ajena", account_type=AccountType.ASSET,
        )
        self.base = f"/api/accounting/companies/{self.company.pk}/"
        self.entries_url = self.base + "journal-entries/"
        self.drafts_url = self.entries_url + "drafts/"
        self.payload = {
            "accounting_date": "2026-11-02",
            "description": "Aporte inicial de capital",
            "lines": [
                {"account": self.cash.pk, "description": "Ingreso en caja", "debit": "100000.25", "credit": "0.00"},
                {"account": self.capital.pk, "description": "Aporte de capital", "debit": "0.00", "credit": "100000.25"},
            ],
        }

    def create_draft(self, payload=None):
        """Crea un borrador por la API y devuelve su detalle.

        @version 1.0
        """
        response = self.client.post(self.entries_url, self.payload if payload is None else payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data

    def test_create_manual_entry_persists_header_and_lines(self):
        """Guarda los datos y devuelve identidad, estado, importes y cuentas.

        @version 1.0
        """
        data = self.create_draft()
        entry = JournalEntry.objects.get(pk=data["id"])
        self.assertEqual(data["status"], EntryStatus.DRAFT)
        self.assertEqual(data["source_type"], EntryOrigin.MANUAL)
        self.assertEqual(data["number"], 1)
        self.assertEqual(data["currency"], Currency.ARS)
        self.assertEqual(data["created_by"], self.user.pk)
        self.assertEqual(entry.company, self.company)
        self.assertEqual(str(entry.accounting_date), self.payload["accounting_date"])
        self.assertEqual(entry.description, self.payload["description"])
        lines = list(entry.lines.order_by("pk"))
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].account, self.cash)
        self.assertEqual(lines[1].account, self.capital)
        self.assertEqual(lines[0].debit, Decimal("100000.25"))
        self.assertEqual(lines[0].credit, Decimal("0.00"))
        self.assertEqual(lines[1].debit, Decimal("0.00"))
        self.assertEqual(lines[1].credit, Decimal("100000.25"))
        self.assertEqual(lines[0].description, "Ingreso en caja")
        self.assertEqual(data["lines"][0]["account_code"], self.cash.code)
        self.assertEqual(data["lines"][0]["account_name"], self.cash.name)

    def test_numbering_is_sequential_and_independent_per_company(self):
        """Reutiliza la numeración del modelo dentro de cada compañía.

        @version 1.0
        """
        first = self.create_draft()
        second = self.create_draft()
        CompanyMember.objects.create(
            user=self.user, company=self.other_company,
            role=CompanyRole.objects.get(code="member"),
        )
        response = self.client.post(
            f"/api/accounting/companies/{self.other_company.pk}/journal-entries/",
            {**self.payload, "lines": []}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual([first["number"], second["number"], response.data["number"]], [1, 2, 1])

    def test_internal_fields_cannot_be_controlled_by_the_client(self):
        """Ignora los campos fuera del contrato y conserva los valores internos.

        @version 1.0
        """
        data = self.create_draft({
            **self.payload, "company": str(self.other_company.pk), "number": 999,
            "status": "POSTED", "source_type": "INVOICE", "source_id": "external",
            "created_by": str(uuid.uuid4()), "reversal_of": 999,
        })
        entry = JournalEntry.objects.get(pk=data["id"])
        self.assertEqual(entry.company, self.company)
        self.assertEqual(entry.number, 1)
        self.assertEqual(entry.status, EntryStatus.DRAFT)
        self.assertEqual(entry.source_type, EntryOrigin.MANUAL)
        self.assertIsNone(entry.source_id)
        self.assertIsNone(entry.reversal_of)
        self.assertEqual(entry.created_by, self.user)

    def test_invalid_second_line_rolls_back_header_and_first_line(self):
        """Un rechazo del modelo no deja cabecera, líneas ni número consumido.

        @version 1.0
        """
        payload = deepcopy(self.payload)
        payload["lines"][1].update(debit="1.00", credit="1.00")
        response = self.client.post(self.entries_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("lines", response.data)
        self.assertFalse(JournalEntry.objects.exists())
        self.assertFalse(JournalLine.objects.exists())
        self.assertEqual(self.create_draft()["number"], 1)

    def test_rejects_foreign_and_nonexistent_accounts(self):
        """Rechaza referencias inexistentes o de otra Company sin persistir.

        @version 1.0
        """
        for account_id in (self.foreign.pk, self.foreign.pk + 1000):
            with self.subTest(account=account_id):
                payload = deepcopy(self.payload)
                payload["lines"][1]["account"] = account_id
                response = self.client.post(self.entries_url, payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertFalse(JournalEntry.objects.exists())
                self.assertFalse(JournalLine.objects.exists())

    def test_rejects_inactive_accounts(self):
        """Reutiliza la validación del modelo para cuentas inactivas.

        @version 1.0
        """
        self.capital.is_active = False
        self.capital.save(update_fields=("is_active",))
        response = self.client.post(self.entries_url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(JournalEntry.objects.exists())
        self.assertFalse(JournalLine.objects.exists())

    def test_rejects_invalid_amounts_without_partial_creation(self):
        """Respeta la precisión decimal y el constraint Debe o Haber del modelo.

        @version 1.0
        """
        for debit, credit in (
            ("-1.00", "0.00"), ("0.00", "-1.00"), ("0.00", "0.00"),
            ("1.00", "1.00"), ("1.001", "0.00"), ("10000000000000000.00", "0.00"),
        ):
            with self.subTest(debit=debit, credit=credit):
                payload = deepcopy(self.payload)
                payload["lines"][1].update(debit=debit, credit=credit)
                response = self.client.post(self.entries_url, payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertFalse(JournalEntry.objects.exists())
                self.assertFalse(JournalLine.objects.exists())

    def test_required_fields_and_currency_follow_the_model(self):
        """Exige fecha, conceptos y líneas y sólo admite la moneda soportada.

        @version 1.0
        """
        for field in ("accounting_date", "description", "lines"):
            with self.subTest(field=field):
                payload = deepcopy(self.payload)
                del payload[field]
                response = self.client.post(self.entries_url, payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)
        payload = deepcopy(self.payload)
        del payload["lines"][0]["description"]
        self.assertEqual(self.client.post(self.entries_url, payload, format="json").status_code, 400)
        self.assertEqual(self.client.post(self.entries_url, {**self.payload, "currency": "USD"}, format="json").status_code, 400)
        self.assertFalse(JournalEntry.objects.exists())

    def test_incomplete_and_unbalanced_drafts_defer_publication_rules(self):
        """Guarda cero, uno o dos movimientos desbalanceados sin publicarlos.

        @version 1.0
        """
        unbalanced = deepcopy(self.payload["lines"])
        unbalanced[1]["credit"] = "1.00"
        for lines in ([], self.payload["lines"][:1], unbalanced):
            with self.subTest(lines=lines):
                draft = self.create_draft({**self.payload, "lines": lines})
                response = self.client.post(f"{self.entries_url}{draft['id']}/publish/")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.data, {"code": "NEX-ACC-003"})
                self.assertEqual(JournalEntry.objects.get(pk=draft["id"]).status, EntryStatus.DRAFT)

    def test_create_requires_company_membership_before_payload_validation(self):
        """Un usuario sin acceso no puede crear ni validar datos en otra Company.

        @version 1.0
        """
        url = f"/api/accounting/companies/{self.other_company.pk}/journal-entries/"
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(JournalEntry.objects.exists())

    def test_list_and_detail_recover_only_authorized_drafts(self):
        """Recupera borradores con líneas y mantiene el historial sin cambios.

        @version 1.0
        """
        first = self.create_draft()
        earlier = self.create_draft({**self.payload, "accounting_date": "2026-11-01"})
        posted = self.create_draft()
        self.client.post(f"{self.entries_url}{posted['id']}/publish/")
        foreign = JournalEntry.objects.create(
            company=self.other_company, accounting_date="2026-11-02", description="Ajeno",
        )
        response = self.client.get(self.drafts_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [earlier["id"], first["id"]])
        detail = self.client.get(f"{self.drafts_url}{first['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data, first)
        for entry_id in (posted["id"], foreign.pk):
            self.assertEqual(self.client.get(f"{self.drafts_url}{entry_id}/").status_code, 404)
        self.assertEqual(self.client.get(f"{self.entries_url}{first['id']}/").status_code, 404)
        self.assertEqual(self.client.get(self.entries_url, {"status": "DRAFT"}).data, [])
        self.assertEqual([row["id"] for row in self.client.get(self.entries_url).data], [posted["id"]])

    def test_foreign_drafts_cannot_be_queried_or_published(self):
        """Rechaza acceso por URL ajena y por ID ajeno bajo una URL autorizada.

        @version 1.0
        """
        foreign = JournalEntry.objects.create(
            company=self.other_company, accounting_date="2026-11-02", description="Ajeno",
        )
        base = f"/api/accounting/companies/{self.other_company.pk}/journal-entries/"
        for url in (base + "drafts/", f"{base}drafts/{foreign.pk}/"):
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(f"{base}{foreign.pk}/publish/").status_code, 403)
        self.assertEqual(self.client.get(f"{self.drafts_url}{foreign.pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"{self.entries_url}{foreign.pk}/publish/").status_code, 404)
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, EntryStatus.DRAFT)

    def test_new_operations_require_authentication(self):
        """Exige sesión para crear, listar y detallar borradores.

        @version 1.0
        """
        draft = self.create_draft()
        anonymous = APIClient()
        self.assertEqual(anonymous.post(self.entries_url, self.payload, format="json").status_code, 401)
        for url in (self.drafts_url, f"{self.drafts_url}{draft['id']}/"):
            self.assertEqual(anonymous.get(url).status_code, 401)

    def test_publish_connects_created_draft_to_history_and_all_reports(self):
        """Excluye borradores y agrega el asiento a cada consulta tras publicarlo.

        @version 1.0
        """
        draft = self.create_draft()
        report_urls = (
            self.base + "reports/daily-journal/",
            self.base + f"reports/general-ledger/{self.cash.pk}/",
            self.base + "reports/trial-balance/",
        )
        for url in (self.entries_url, *report_urls):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, [])
        response = self.client.post(f"{self.entries_url}{draft['id']}/publish/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"id": draft["id"], "number": draft["number"], "status": "POSTED"})
        self.assertEqual(self.client.get(self.drafts_url).data, [])
        self.assertEqual(self.client.get(f"{self.drafts_url}{draft['id']}/").status_code, 404)
        history = self.client.get(self.entries_url).data
        self.assertEqual([row["id"] for row in history], [draft["id"]])
        diary, ledger, trial = [self.client.get(url).data for url in report_urls]
        self.assertEqual(diary[0]["id"], draft["id"])
        self.assertEqual(len(diary[0]["lines"]), 2)
        self.assertEqual(ledger[0]["entry_number"], draft["number"])
        self.assertEqual(Decimal(ledger[0]["balance"]), Decimal("100000.25"))
        by_account = {row["account"]: row for row in trial}
        self.assertEqual(Decimal(by_account[self.cash.pk]["total_debit"]), Decimal("100000.25"))
        self.assertEqual(Decimal(by_account[self.capital.pk]["total_credit"]), Decimal("100000.25"))

    def test_draft_queries_do_not_enable_editing_or_deletion(self):
        """Mantiene el alcance de recuperación sin agregar gestión avanzada.

        @version 1.0
        """
        draft = self.create_draft()
        url = f"{self.drafts_url}{draft['id']}/"
        self.assertEqual(self.client.patch(url, {"description": "Cambio"}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)
