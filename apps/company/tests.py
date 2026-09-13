"""
Tests para el alta, las validaciones y la búsqueda de compañías.

@version 1.0
@author Antonio
"""

import uuid

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


VALID_TAX_ID = "20000000001"


class CompanyMemberModelTests(TestCase):
    def setUp(self):
        self.owner_role = CompanyRole.objects.get(code="owner")
        self.member_role = CompanyRole.objects.get(code="member")
        self.company = Company.objects.create(name="Compañía Uno")
        self.other_company = Company.objects.create(name="Compañía Dos")
        self.user = User.objects.create(id=uuid.uuid4(), email="uno@example.com")
        self.other_user = User.objects.create(
            id=uuid.uuid4(), email="dos@example.com"
        )

    def test_initial_roles_exist(self):
        self.assertEqual(
            set(CompanyRole.objects.values_list("code", flat=True)),
            {"owner", "member"},
        )

    def test_creates_company_role(self):
        role = CompanyRole.objects.create(code="auditor")

        self.assertEqual(role.code, "auditor")

    def test_creates_company_member_with_its_role(self):
        membership = CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=self.owner_role,
        )

        self.assertEqual(membership.role, self.owner_role)
        self.assertEqual(list(self.company.memberships.all()), [membership])

    def test_same_user_cannot_be_member_twice_in_a_company(self):
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=self.owner_role,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompanyMember.objects.create(
                    user=self.user,
                    company=self.company,
                    role=self.member_role,
                )

    def test_same_user_can_belong_to_different_companies(self):
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=self.owner_role,
        )
        membership = CompanyMember.objects.create(
            user=self.user,
            company=self.other_company,
            role=self.member_role,
        )

        self.assertEqual(membership.company, self.other_company)

    def test_different_users_can_belong_to_the_same_company(self):
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=self.owner_role,
        )
        membership = CompanyMember.objects.create(
            user=self.other_user,
            company=self.company,
            role=self.member_role,
        )

        self.assertEqual(membership.user, self.other_user)


class CompanyCreateTests(APITestCase):
    url = "/api/companies/"

    def test_create_individual_without_tax_info(self):
        response = self.client.post(
            self.url,
            {"type": "individual", "name": "Autónomo Local"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        company = Company.objects.get(pk=response.data["id"])
        self.assertEqual(company.type, Company.Type.INDIVIDUAL)
        self.assertEqual(company.tax_id, None)
        self.assertEqual(company.legal_name, None)
        self.assertTrue(company.is_active)

    def test_create_organization_with_tax_info(self):
        response = self.client.post(
            self.url,
            {
                "type": "organization",
                "name": "Org Ejemplo",
                "legal_name": "Org Ejemplo S.A.",
                "tax_id": "20-00000000-1",
                "email": "Contacto@Org.Com",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        company = Company.objects.get(pk=response.data["id"])
        self.assertEqual(company.type, Company.Type.ORGANIZATION)
        self.assertEqual(company.legal_name, "Org Ejemplo S.A.")
        self.assertEqual(company.tax_id, VALID_TAX_ID)
        self.assertEqual(company.email, "Contacto@Org.Com")

    def test_create_with_legal_name_and_tax_id_empty(self):
        response = self.client.post(
            self.url,
            {"type": "individual", "name": "Sin Info", "legal_name": "", "tax_id": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        company = Company.objects.get(pk=response.data["id"])
        self.assertEqual(company.legal_name, "")
        self.assertIsNone(company.tax_id)

    def test_structurally_invalid_tax_id_is_rejected(self):
        response = self.client.post(
            self.url,
            {
                "type": "individual",
                "name": "Mal CUIT",
                "tax_id": "20-12345678-9",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "NEX-COM-001")
        self.assertIn("tax_id", response.data["errors"])

    def test_duplicate_tax_id_is_rejected(self):
        Company.objects.create(
            type=Company.Type.INDIVIDUAL,
            name="Primera",
            tax_id=VALID_TAX_ID,
        )

        response = self.client.post(
            self.url,
            {
                "type": "organization",
                "name": "Segunda",
                "tax_id": "20 000000001",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tax_id", response.data["errors"])

    def test_duplicate_tax_id_with_the_same_format_is_rejected(self):
        Company.objects.create(
            type=Company.Type.INDIVIDUAL,
            name="Primera",
            tax_id=VALID_TAX_ID,
        )

        response = self.client.post(
            self.url,
            {
                "type": "organization",
                "name": "Segunda",
                "tax_id": VALID_TAX_ID,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tax_id", response.data["errors"])

    def test_multiple_companies_without_tax_id_are_allowed(self):
        Company.objects.create(
            type=Company.Type.INDIVIDUAL, name="Una", tax_id=None
        )

        response = self.client.post(
            self.url,
            {"type": "individual", "name": "Otra", "tax_id": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_invalid_email_is_rejected(self):
        response = self.client.post(
            self.url,
            {"type": "individual", "name": "Correo Malo", "email": "no-soy-un-email"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["errors"])

    def test_name_is_required(self):
        response = self.client.post(
            self.url,
            {"type": "individual"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data["errors"])

    def test_tax_id_length_and_guard_digit_rejected(self):
        response = self.client.post(
            self.url,
            {"type": "individual", "name": "CUIT Corto", "tax_id": "2001"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tax_id", response.data["errors"])


class CompanyUpdateTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(
            type=Company.Type.INDIVIDUAL,
            name="Primera",
            tax_id=VALID_TAX_ID,
        )
        self.other = Company.objects.create(
            type=Company.Type.ORGANIZATION,
            name="Segunda",
            tax_id="20999999999",
        )

    def test_patch_allows_the_current_tax_id(self):
        response = self.client.patch(
            f"/api/companies/{self.company.id}/",
            {"tax_id": "20-00000000-1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tax_id"], VALID_TAX_ID)

    def test_patch_rejects_a_tax_id_from_another_company(self):
        response = self.client.patch(
            f"/api/companies/{self.company.id}/",
            {"tax_id": self.other.tax_id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tax_id", response.data["errors"])

    def test_patch_without_tax_id_keeps_the_current_value(self):
        response = self.client.patch(
            f"/api/companies/{self.company.id}/",
            {"name": "Primera Editada"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.company.refresh_from_db()
        self.assertEqual(self.company.tax_id, VALID_TAX_ID)


class CompanySearchTests(APITestCase):
    url = "/api/companies/search/"

    def setUp(self):
        self.company = Company.objects.create(
            type=Company.Type.ORGANIZATION,
            name="Acme SRL",
            legal_name="Acme Sociedad de Responsabilidad Limitada",
            tax_id=VALID_TAX_ID,
        )
        self.other = Company.objects.create(
            type=Company.Type.INDIVIDUAL,
            name="María Pérez",
            legal_name=None,
            tax_id=None,
        )

    def test_search_by_name_returns_matches(self):
        response = self.client.get(self.url, {"q": "acme"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data]
        self.assertIn(str(self.company.id), ids)

    def test_search_by_legal_name_returns_matches(self):
        response = self.client.get(
            self.url, {"q": "responsabilidad limitada"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data]
        self.assertIn(str(self.company.id), ids)

    def test_search_by_tax_id_locates_company(self):
        response = self.client.get(
            self.url, {"q": "20-00000000-1"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data]
        self.assertIn(str(self.company.id), ids)

    def test_search_tolerates_extra_spaces(self):
        response = self.client.get(self.url, {"q": "  acme  srl  "}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data]
        self.assertIn(str(self.company.id), ids)
        self.assertNotIn(str(self.other.id), ids)

    def test_search_without_results_returns_empty_list(self):
        response = self.client.get(self.url, {"q": "noexiste"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_empty_query_is_handled_controlled(self):
        response = self.client.get(self.url, {"q": ""}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_missing_query_is_handled_controlled(self):
        response = self.client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])
