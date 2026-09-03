"""Tests para el alta y las validaciones de compañías."""

from rest_framework import status
from rest_framework.test import APITestCase

from apps.company.models import Company


VALID_TAX_ID = "20000000001"
VALID_TAX_ID_OTHER = "20999999999"
INVALID_TAX_ID = "20123456789"


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
        self.assertEqual(company.email, "contacto@org.com")

    def test_create_with_legal_name_and_tax_id_empty(self):
        response = self.client.post(
            self.url,
            {"type": "individual", "name": "Sin Info", "legal_name": "", "tax_id": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        company = Company.objects.get(pk=response.data["id"])
        self.assertIsNone(company.legal_name)
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
