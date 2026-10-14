"""Pruebas de actualización de Company."""

import uuid

from rest_framework import status
from rest_framework.test import APITestCase

from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


VALID_TAX_ID = "20000000001"


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
