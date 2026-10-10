"""Pruebas de creación y validación de Company."""

import uuid
from unittest.mock import patch

from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APITestCase

from apps.company.models import Company, CompanyMember
from apps.users.models import User


VALID_TAX_ID = "20000000001"


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
