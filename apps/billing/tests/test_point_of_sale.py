import uuid
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.billing.enums import VATCondition
from apps.billing.models import FiscalProfile, PointOfSale
from apps.billing.services.numbering import assign_point_of_sale_number
from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


class PointOfSaleModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Empresa POS")
        self.fiscal_profile = FiscalProfile.objects.create(
            company=self.company,
            vat_condition=VATCondition.REGISTERED_RESPONSIBLE,
        )

    def test_first_point_of_sale_is_00001(self):
        point_of_sale = assign_point_of_sale_number(self.fiscal_profile)

        self.assertEqual(point_of_sale.number, 1)
        self.assertEqual(point_of_sale.formatted_number, "00001")

    def test_points_of_sale_increment_sequentially(self):
        first = assign_point_of_sale_number(self.fiscal_profile)
        second = assign_point_of_sale_number(self.fiscal_profile)

        self.assertEqual(first.number, 1)
        self.assertEqual(second.number, 2)
        self.assertEqual(second.formatted_number, "00002")

    def test_number_is_unique_per_fiscal_profile(self):
        PointOfSale.objects.create(fiscal_profile=self.fiscal_profile, number=1)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PointOfSale.objects.create(fiscal_profile=self.fiscal_profile, number=1)

    def test_same_number_allowed_across_different_fiscal_profiles(self):
        other_company = Company.objects.create(name="Otra empresa")
        other_profile = FiscalProfile.objects.create(
            company=other_company,
            vat_condition=VATCondition.EXEMPT,
        )

        PointOfSale.objects.create(fiscal_profile=self.fiscal_profile, number=1)
        # No debe levantar IntegrityError: el constraint es por perfil fiscal.
        PointOfSale.objects.create(fiscal_profile=other_profile, number=1)


class PointOfSaleAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Empresa POS API")
        self.fiscal_profile = FiscalProfile.objects.create(
            company=self.company,
            vat_condition=VATCondition.MONOTAX,
        )
        self.user = User.objects.create(id=uuid.uuid4(), email="pos@example.com")
        self.owner_role = CompanyRole.objects.get(code="owner")
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=self.owner_role,
        )
        self.client.force_authenticate(user=self.user)
        self.list_url = f"/api/billing/companies/{self.company.id}/points-of-sale/"

    def test_create_assigns_number_automatically(self):
        response = self.client.post(self.list_url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["number"], "00001")
        self.assertTrue(response.data["is_active"])

    def test_list_returns_created_points_of_sale(self):
        self.client.post(self.list_url, {}, format="json")
        self.client.post(self.list_url, {}, format="json")

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual({item["number"] for item in response.data}, {"00001", "00002"})

    def test_activate_and_deactivate(self):
        created = self.client.post(self.list_url, {}, format="json").data
        pos_id = created["id"]

        deactivate_response = self.client.post(f"{self.list_url}{pos_id}/deactivate/")
        self.assertEqual(deactivate_response.status_code, status.HTTP_200_OK)
        self.assertFalse(deactivate_response.data["is_active"])

        activate_response = self.client.post(f"{self.list_url}{pos_id}/activate/")
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        self.assertTrue(activate_response.data["is_active"])

    def test_user_without_membership_cannot_create(self):
        other_company = Company.objects.create(name="Empresa ajena")
        other_url = f"/api/billing/companies/{other_company.id}/points-of-sale/"

        response = self.client.post(other_url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)