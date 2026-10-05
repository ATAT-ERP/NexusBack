import uuid

from django.db import IntegrityError, transaction
from django.test import override_settings
from django.urls import include, path
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounting.enums import AccountType
from apps.accounting.models import Account
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
        self.assertEqual(
            anonymous_client.get(self.list_url).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
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

        @version 1.0
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
        self.assertIn("code", response.data)

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
        self.assertEqual(self.client.get(other_url).status_code, status.HTTP_403_FORBIDDEN)
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
        self.assertEqual(
            self.client.get(f"{self.list_url}{account.pk}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

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

        @version 1.0
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
        self.assertIn("code", response.data)
        account.refresh_from_db()
        self.assertEqual(account.code, "1.1.02")
