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
