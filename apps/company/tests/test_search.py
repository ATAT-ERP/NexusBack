"""Pruebas de búsqueda de Company."""

import uuid

from rest_framework import status
from rest_framework.test import APITestCase

from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


VALID_TAX_ID = "20000000001"


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
        CompanyMember.objects.create(
            user=self.user,
            company=self.other,
            role=CompanyRole.objects.get(code="member"),
        )
        self.client.force_authenticate(user=self.user)

    def test_search_by_name_returns_matches(self):
        response = self.client.get(self.url, {"q": "acme"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data]
        self.assertIn(str(self.company.id), ids)
        self.assertEqual(response.data[0]["my_role"], "owner")

    def test_search_exposes_membership_role_for_each_company(self):
        response = self.client.get(self.url, {"q": "María"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["my_role"], "member")

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

    def test_search_defaults_to_active_companies(self):
        self.company.is_active = False
        self.company.save()

        response = self.client.get(self.url, {"q": "Acme"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_search_filters_inactive_companies_by_state_and_type(self):
        self.company.is_active = False
        self.company.save()

        response = self.client.get(
            self.url,
            {"q": "Acme", "is_active": "false", "type": "organization"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([row["id"] for row in response.data], [str(self.company.id)])

    def test_search_includes_inactive_companies_when_requested(self):
        self.company.is_active = False
        self.company.save()

        response = self.client.get(
            self.url, {"q": "Acme", "is_active": "all"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([row["id"] for row in response.data], [str(self.company.id)])

    def test_search_rejects_invalid_filters_with_company_error_contract(self):
        response = self.client.get(
            self.url, {"q": "Acme", "type": "business"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "NEX-COM-001")
        self.assertIn("type", response.data["errors"])
