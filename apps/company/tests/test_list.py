"""Pruebas del listado y los filtros de Company."""

import uuid

from rest_framework import status
from rest_framework.test import APITestCase

from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


class CompanyListTests(APITestCase):
    url = "/api/companies/"

    def setUp(self):
        self.user = User.objects.create(id=uuid.uuid4(), email="portfolio@example.com")
        owner_role = CompanyRole.objects.get(code="owner")
        member_role = CompanyRole.objects.get(code="member")
        self.companies = [
            Company.objects.create(
                type=Company.Type.INDIVIDUAL,
                name="Persona activa",
            ),
            Company.objects.create(
                type=Company.Type.ORGANIZATION,
                name="Organización activa",
            ),
            Company.objects.create(
                type=Company.Type.INDIVIDUAL,
                name="Persona inactiva",
                is_active=False,
            ),
            Company.objects.create(
                type=Company.Type.ORGANIZATION,
                name="Organización inactiva",
                is_active=False,
            ),
        ]
        for company, role in zip(
            self.companies,
            (owner_role, member_role, member_role, owner_role),
        ):
            CompanyMember.objects.create(
                user=self.user,
                company=company,
                role=role,
            )
        self.client.force_authenticate(user=self.user)

    def test_default_list_returns_active_companies_of_both_types(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {row["id"] for row in response.data},
            {str(company.id) for company in self.companies[:2]},
        )

    def test_list_filters_inactive_companies(self):
        response = self.client.get(self.url, {"is_active": "false"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {row["id"] for row in response.data},
            {str(company.id) for company in self.companies[2:]},
        )

    def test_list_can_include_both_states_and_filter_by_type(self):
        response = self.client.get(
            self.url,
            {"is_active": "all", "type": "individual"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {row["id"] for row in response.data},
            {str(self.companies[0].id), str(self.companies[2].id)},
        )

    def test_list_exposes_the_user_role_per_company(self):
        response = self.client.get(self.url, {"is_active": "all"})
        roles = {row["id"]: row["my_role"] for row in response.data}

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(roles[str(self.companies[0].id)], "owner")
        self.assertEqual(roles[str(self.companies[1].id)], "member")
        self.assertEqual(roles[str(self.companies[2].id)], "member")
        self.assertEqual(roles[str(self.companies[3].id)], "owner")

    def test_list_rejects_invalid_state_and_type(self):
        for params, field in (
            ({"is_active": "yes"}, "is_active"),
            ({"type": "business"}, "type"),
        ):
            with self.subTest(params=params):
                response = self.client.get(self.url, params)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.data["code"], "NEX-COM-001")
                self.assertIn(field, response.data["errors"])
