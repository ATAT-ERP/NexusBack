"""Pruebas de acceso y permisos de Company."""

import uuid

from rest_framework import status
from rest_framework.test import APITestCase

from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


VALID_TAX_ID = "20000000001"


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
        self.assertEqual(detail.data["my_role"], "member")
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
