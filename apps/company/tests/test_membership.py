"""Pruebas de membresías y roles de Company."""

import uuid

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


VALID_TAX_ID = "20000000001"


class CompanyMemberModelTests(TestCase):
    def setUp(self):
        self.owner_role = CompanyRole.objects.get(code="owner")
        self.member_role = CompanyRole.objects.get(code="member")
        self.company = Company.objects.create(name="Compañía Uno")
        self.other_company = Company.objects.create(name="Compañía Dos")
        self.user = User.objects.create(id=uuid.uuid4(), email="uno@example.com")
        self.other_user = User.objects.create(
            id=uuid.uuid4(), email="dos@example.com"
        )

    def test_initial_roles_exist(self):
        self.assertEqual(
            set(CompanyRole.objects.values_list("code", flat=True)),
            {"owner", "member"},
        )

    def test_creates_company_role(self):
        role = CompanyRole.objects.create(code="auditor")

        self.assertEqual(role.code, "auditor")

    def test_creates_company_member_with_its_role(self):
        membership = CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=self.owner_role,
        )

        self.assertEqual(membership.role, self.owner_role)
        self.assertEqual(list(self.company.memberships.all()), [membership])

    def test_same_user_cannot_be_member_twice_in_a_company(self):
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=self.owner_role,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompanyMember.objects.create(
                    user=self.user,
                    company=self.company,
                    role=self.member_role,
                )

    def test_same_user_can_belong_to_different_companies(self):
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=self.owner_role,
        )
        membership = CompanyMember.objects.create(
            user=self.user,
            company=self.other_company,
            role=self.member_role,
        )

        self.assertEqual(membership.company, self.other_company)

    def test_different_users_can_belong_to_the_same_company(self):
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=self.owner_role,
        )
        membership = CompanyMember.objects.create(
            user=self.other_user,
            company=self.company,
            role=self.member_role,
        )

        self.assertEqual(membership.user, self.other_user)
