"""
Tests para el alta, las validaciones y la búsqueda de compañías.

@version 1.0
@author Antonio
"""

import uuid
from unittest.mock import patch

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

    def setUp(self):
        self.user = User.objects.create(id=uuid.uuid4(), email="creator@example.com")
        self.client.force_authenticate(user=self.user)

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


class CompanyOwnerCreationTests(APITestCase):
    url = "/api/companies/"

    def setUp(self):
        self.user = User.objects.create(id=uuid.uuid4(), email="owner@example.com")

    def test_authenticated_post_creates_an_owner_membership(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {"type": "individual", "name": "Compañía con owner"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        company = Company.objects.get(pk=response.data["id"])
        membership = CompanyMember.objects.get(company=company)
        self.assertEqual(CompanyMember.objects.filter(company=company).count(), 1)
        self.assertEqual(membership.user, self.user)
        self.assertEqual(membership.company, company)
        self.assertEqual(membership.role.code, "owner")

    def test_unauthenticated_post_does_not_create_a_company(self):
        response = self.client.post(
            self.url,
            {"type": "individual", "name": "Sin autenticación"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Company.objects.filter(name="Sin autenticación").exists())

    def test_membership_failure_rolls_back_the_company(self):
        self.client.force_authenticate(user=self.user)

        with patch(
            "apps.company.api.views.CompanyMember.objects.create",
            side_effect=IntegrityError,
        ):
            with self.assertRaises(IntegrityError):
                self.client.post(
                    self.url,
                    {"type": "individual", "name": "Compañía revertida"},
                    format="json",
                )

        self.assertFalse(Company.objects.filter(name="Compañía revertida").exists())


class CompanyUpdateTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(id=uuid.uuid4(), email="owner@example.com")
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
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=CompanyRole.objects.get(code="owner"),
        )
        self.client.force_authenticate(user=self.user)

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
        self.user = User.objects.create(id=uuid.uuid4(), email="owner@example.com")
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
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=CompanyRole.objects.get(code="owner"),
        )
        self.client.force_authenticate(user=self.user)

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


class CompanyAccessTests(APITestCase):
    list_url = "/api/companies/"
    search_url = "/api/companies/search/"

    def setUp(self):
        self.owner = User.objects.create(id=uuid.uuid4(), email="owner@example.com")
        self.member = User.objects.create(id=uuid.uuid4(), email="member@example.com")
        self.stranger = User.objects.create(id=uuid.uuid4(), email="stranger@example.com")
        self.company = Company.objects.create(name="Cliente Uno")
        self.other_company = Company.objects.create(name="Cliente Confidencial")
        CompanyMember.objects.create(
            user=self.owner,
            company=self.company,
            role=CompanyRole.objects.get(code="owner"),
        )
        CompanyMember.objects.create(
            user=self.member,
            company=self.company,
            role=CompanyRole.objects.get(code="member"),
        )
        CompanyMember.objects.create(
            user=self.stranger,
            company=self.other_company,
            role=CompanyRole.objects.get(code="owner"),
        )

    def test_all_company_operations_require_authentication(self):
        urls = (
            self.list_url,
            self.search_url,
            f"/api/companies/{self.company.id}/",
        )
        requests = (
            ("get", urls[0], None),
            ("get", urls[1], {"q": "Cliente"}),
            ("post", urls[0], {"name": "Sin usuario"}),
            ("get", urls[2], None),
            ("put", urls[2], {"name": "Editada"}),
            ("patch", urls[2], {"name": "Editada"}),
            ("delete", urls[2], None),
        )

        for method, url, data in requests:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, data, format="json")
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_and_search_only_return_companies_with_membership(self):
        self.client.force_authenticate(user=self.owner)

        listed = self.client.get(self.list_url, {"is_active": "all"})
        searched = self.client.get(self.search_url, {"q": "Cliente"})

        self.assertEqual([row["id"] for row in listed.data], [str(self.company.id)])
        self.assertEqual([row["id"] for row in searched.data], [str(self.company.id)])

    def test_nonmember_cannot_retrieve_company_by_uuid(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(f"{self.list_url}{self.other_company.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "NEX-COM-004")

    def test_member_can_read_but_cannot_update_or_deactivate_company(self):
        self.client.force_authenticate(user=self.member)

        detail = self.client.get(f"{self.list_url}{self.company.id}/")
        update = self.client.patch(
            f"{self.list_url}{self.company.id}/", {"name": "Editada"}, format="json"
        )
        deletion = self.client.delete(f"{self.list_url}{self.company.id}/")

        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(update.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(deletion.status_code, status.HTTP_403_FORBIDDEN)
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, "Cliente Uno")
        self.assertTrue(self.company.is_active)

    def test_owner_can_deactivate_company_and_membership_is_preserved(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.delete(f"{self.list_url}{self.company.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.company.refresh_from_db()
        self.assertFalse(self.company.is_active)
        self.assertTrue(
            CompanyMember.objects.filter(user=self.owner, company=self.company).exists()
        )

    def test_inactive_company_remains_readable_but_rejects_writes(self):
        self.company.is_active = False
        self.company.save()
        self.client.force_authenticate(user=self.owner)

        detail = self.client.get(f"{self.list_url}{self.company.id}/")
        update = self.client.patch(
            f"{self.list_url}{self.company.id}/", {"name": "Editada"}, format="json"
        )

        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(update.status_code, status.HTTP_403_FORBIDDEN)
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, "Cliente Uno")
