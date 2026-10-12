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


class PointOfSaleIsolationTests(APITestCase):
    def setUp(self):
        owner_role = CompanyRole.objects.get(code="owner")
        self.company = Company.objects.create(name="Empresa A")
        self.point_of_sale = assign_point_of_sale_number(
            FiscalProfile.objects.create(
                company=self.company, vat_condition=VATCondition.MONOTAX
            )
        )
        self.user = User.objects.create(id=uuid.uuid4(), email="pos-a@example.com")
        CompanyMember.objects.create(
            user=self.user, company=self.company, role=owner_role
        )

        self.other_company = Company.objects.create(name="Empresa B")
        FiscalProfile.objects.create(
            company=self.other_company, vat_condition=VATCondition.MONOTAX
        )
        self.other_user = User.objects.create(id=uuid.uuid4(), email="pos-b@example.com")
        CompanyMember.objects.create(
            user=self.other_user, company=self.other_company, role=owner_role
        )

        self.url = (
            f"/api/billing/companies/{self.company.id}/points-of-sale/"
            f"{self.point_of_sale.id}/"
        )
        # Misma pk consultada desde la Company B.
        self.other_url = (
            f"/api/billing/companies/{self.other_company.id}/points-of-sale/"
            f"{self.point_of_sale.id}/"
        )

    def test_member_of_other_company_cannot_read_point_of_sale(self):
        self.client.force_authenticate(user=self.other_user)

        for url, expected in (
            (self.url, status.HTTP_403_FORBIDDEN),
            (self.other_url, status.HTTP_404_NOT_FOUND),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, expected)

    def test_member_can_read_own_point_of_sale(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.point_of_sale.id)

    def test_member_of_other_company_cannot_activate_point_of_sale(self):
        PointOfSale.objects.filter(pk=self.point_of_sale.pk).update(is_active=False)
        self.client.force_authenticate(user=self.other_user)

        for url, expected in (
            (self.url, status.HTTP_403_FORBIDDEN),
            (self.other_url, status.HTTP_404_NOT_FOUND),
        ):
            with self.subTest(url=url):
                response = self.client.post(f"{url}activate/")

                self.assertEqual(response.status_code, expected)
                self.point_of_sale.refresh_from_db()
                self.assertFalse(self.point_of_sale.is_active)

    def test_member_can_activate_own_point_of_sale(self):
        PointOfSale.objects.filter(pk=self.point_of_sale.pk).update(is_active=False)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(f"{self.url}activate/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.point_of_sale.refresh_from_db()
        self.assertTrue(self.point_of_sale.is_active)

    def test_member_of_other_company_cannot_deactivate_point_of_sale(self):
        self.client.force_authenticate(user=self.other_user)

        for url, expected in (
            (self.url, status.HTTP_403_FORBIDDEN),
            (self.other_url, status.HTTP_404_NOT_FOUND),
        ):
            with self.subTest(url=url):
                response = self.client.post(f"{url}deactivate/")

                self.assertEqual(response.status_code, expected)
                self.point_of_sale.refresh_from_db()
                self.assertTrue(self.point_of_sale.is_active)

    def test_member_can_deactivate_own_point_of_sale(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(f"{self.url}deactivate/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.point_of_sale.refresh_from_db()
        self.assertFalse(self.point_of_sale.is_active)

    def test_non_member_cannot_list_points_of_sale(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(
            f"/api/billing/companies/{self.company.id}/points-of-sale/"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_never_includes_points_of_sale_of_other_company(self):
        assign_point_of_sale_number(FiscalProfile.objects.get(company=self.company))
        own_point_of_sale = assign_point_of_sale_number(
            FiscalProfile.objects.get(company=self.other_company)
        )
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(
            f"/api/billing/companies/{self.other_company.id}/points-of-sale/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [own_point_of_sale.id])