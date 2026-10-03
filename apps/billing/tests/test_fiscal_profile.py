import uuid

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.billing.enums import VATCondition
from apps.billing.models import FiscalProfile
from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


class FiscalProfileModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Empresa fiscal",
            legal_name="Empresa Fiscal S.A.",
            tax_id="20000000001",
        )

    def test_creates_profile_with_optional_fields_omitted(self):
        profile = FiscalProfile.objects.create(
            company=self.company,
            vat_condition=VATCondition.REGISTERED_RESPONSIBLE,
        )

        self.assertEqual(profile.company, self.company)
        self.assertEqual(profile.gross_income, "")
        self.assertIsNone(profile.business_start_date)
        self.assertEqual(self.company.fiscal_profile, profile)

    def test_company_can_have_only_one_profile(self):
        FiscalProfile.objects.create(
            company=self.company,
            vat_condition=VATCondition.FINAL_CONSUMER,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FiscalProfile.objects.create(
                    company=self.company,
                    vat_condition=VATCondition.FINAL_CONSUMER,
                )

    def test_profile_does_not_duplicate_company_general_fields(self):
        field_names = {field.name for field in FiscalProfile._meta.fields}

        self.assertTrue(
            {"company", "vat_condition", "gross_income", "business_start_date"}
            <= field_names
        )
        self.assertFalse({"tax_id", "legal_name", "email", "phone"} & field_names)
        self.assertEqual(self.company.tax_id, "20000000001")
        self.assertEqual(self.company.legal_name, "Empresa Fiscal S.A.")


class FiscalProfileAPITests(APITestCase):
    def setUp(self):
        self.url = "/api/billing/companies/{}/fiscal-profile/"
        self.user = User.objects.create(id=uuid.uuid4(), email="fiscal@example.com")
        self.company = Company.objects.create(name="Empresa Uno")
        self.other_company = Company.objects.create(name="Empresa Dos")
        self.owner_role = CompanyRole.objects.get(code="owner")
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=self.owner_role,
        )
        self.client.force_authenticate(user=self.user)

    def test_authorized_user_can_create_read_and_update_profile(self):
        response = self.client.post(
            self.url.format(self.company.id),
            {
                "vat_condition": VATCondition.REGISTERED_RESPONSIBLE,
                "gross_income": "123-456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["company"], str(self.company.id))
        self.assertEqual(response.data["vat_condition"], VATCondition.REGISTERED_RESPONSIBLE)

        response = self.client.get(self.url.format(self.company.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["gross_income"], "123-456")

        response = self.client.patch(
            self.url.format(self.company.id),
            {"vat_condition": VATCondition.MONOTAX, "gross_income": ""},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        profile = FiscalProfile.objects.get(company=self.company)
        self.assertEqual(profile.vat_condition, VATCondition.MONOTAX)
        self.assertEqual(profile.gross_income, "")

    def test_rejects_unsupported_vat_condition(self):
        response = self.client.post(
            self.url.format(self.company.id),
            {"vat_condition": 2},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("vat_condition", response.data)

    def test_company_fields_in_profile_payload_do_not_update_company(self):
        response = self.client.post(
            self.url.format(self.company.id),
            {
                "vat_condition": VATCondition.EXEMPT,
                "tax_id": "20000000001",
                "legal_name": "Alteración",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.company.refresh_from_db()
        self.assertIsNone(self.company.tax_id)
        self.assertIsNone(self.company.legal_name)

    def test_user_without_company_membership_cannot_operate_on_profile(self):
        FiscalProfile.objects.create(
            company=self.other_company,
            vat_condition=VATCondition.EXEMPT,
        )

        for response in (
            self.client.get(self.url.format(self.other_company.id)),
            self.client.post(
                self.url.format(self.other_company.id),
                {"vat_condition": VATCondition.EXEMPT},
                format="json",
            ),
            self.client.patch(
                self.url.format(self.other_company.id),
                {"vat_condition": VATCondition.MONOTAX},
                format="json",
            ),
        ):
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_api_rejects_duplicate_profile(self):
        FiscalProfile.objects.create(
            company=self.company,
            vat_condition=VATCondition.EXEMPT,
        )

        response = self.client.post(
            self.url.format(self.company.id),
            {"vat_condition": VATCondition.MONOTAX},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
