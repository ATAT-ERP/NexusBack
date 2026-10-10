"""Pruebas de membresías y roles de Company."""

import uuid

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

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


class CompanyMemberAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create(id=uuid.uuid4(), email="owner@example.com")
        self.second_owner = User.objects.create(
            id=uuid.uuid4(), email="owner2@example.com"
        )
        self.member = User.objects.create(id=uuid.uuid4(), email="member@example.com")
        self.candidate = User.objects.create(
            id=uuid.uuid4(), email="candidate@example.com"
        )
        self.company = Company.objects.create(name="Company Uno")
        self.other_company = Company.objects.create(name="Company Dos")
        owner_role = CompanyRole.objects.get(code="owner")
        member_role = CompanyRole.objects.get(code="member")
        CompanyMember.objects.create(
            user=self.owner,
            company=self.company,
            role=owner_role,
        )
        CompanyMember.objects.create(
            user=self.second_owner,
            company=self.company,
            role=owner_role,
        )
        CompanyMember.objects.create(
            user=self.member,
            company=self.company,
            role=member_role,
        )
        CompanyMember.objects.create(
            user=self.member,
            company=self.other_company,
            role=owner_role,
        )
        self.members_url = f"/api/companies/{self.company.id}/members/"
        self.member_url = f"{self.members_url}{self.member.id}/"
        self.client.force_authenticate(user=self.owner)

    def test_owner_and_member_can_list_company_members(self):
        response = self.client.get(self.members_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        self.assertEqual(
            set(response.data[0]),
            {"user_id", "email", "first_name", "last_name", "role"},
        )
        self.assertNotIn("is_system_admin", response.data[0])

        self.client.force_authenticate(user=self.member)
        member_response = self.client.get(self.members_url)
        self.assertEqual(member_response.status_code, status.HTTP_200_OK)

    def test_listing_members_uses_one_query_for_member_details(self):
        with self.assertNumQueries(2):
            response = self.client.get(self.members_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_owner_can_add_existing_user_with_valid_role(self):
        response = self.client.post(
            self.members_url,
            {"user_id": str(self.candidate.id), "role": "member"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user_id"], str(self.candidate.id))
        self.assertEqual(response.data["role"], "member")
        self.assertTrue(
            CompanyMember.objects.filter(
                company=self.company,
                user=self.candidate,
                role__code="member",
            ).exists()
        )

    def test_owner_can_add_by_trimmed_email_with_default_member_role(self):
        response = self.client.post(
            self.members_url,
            {"email": "  candidate@example.com  "},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user_id"], str(self.candidate.id))
        self.assertEqual(response.data["role"], "member")

    def test_email_lookup_is_case_insensitive(self):
        response = self.client.post(
            self.members_url,
            {"email": "CANDIDATE@EXAMPLE.COM", "role": "member"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user_id"], str(self.candidate.id))

    def test_email_lookup_rejects_unknown_inactive_and_ambiguous_users_generically(self):
        unknown = self.client.post(
            self.members_url,
            {"email": "unknown@example.com"},
            format="json",
        )
        self.candidate.is_active = False
        self.candidate.save(update_fields=["is_active"])
        inactive = self.client.post(
            self.members_url,
            {"email": "candidate@example.com"},
            format="json",
        )
        User.objects.create(id=uuid.uuid4(), email="CANDIDATE@example.com")
        ambiguous = self.client.post(
            self.members_url,
            {"email": "candidate@example.com"},
            format="json",
        )

        self.assertEqual(unknown.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(inactive.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ambiguous.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(unknown.data, inactive.data)
        self.assertEqual(inactive.data, ambiguous.data)

    def test_email_lookup_rejects_duplicate_membership_generically(self):
        response = self.client.post(
            self.members_url,
            {"email": " MEMBER@example.com "},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "NEX-COM-001")
        self.assertEqual(
            str(response.data["errors"]["email"]),
            "No se pudo asociar el usuario.",
        )

    def test_add_rejects_email_and_user_id_together(self):
        response = self.client.post(
            self.members_url,
            {
                "email": "candidate@example.com",
                "user_id": str(self.candidate.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "NEX-COM-001")
        self.assertIn("email", response.data["errors"])

    def test_add_rejects_duplicate_and_unknown_users_without_enumerating_them(self):
        duplicate = self.client.post(
            self.members_url,
            {"user_id": str(self.member.id), "role": "member"},
            format="json",
        )
        unknown = self.client.post(
            self.members_url,
            {"user_id": str(uuid.uuid4()), "role": "member"},
            format="json",
        )

        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(unknown.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(duplicate.data, unknown.data)
        self.assertEqual(duplicate.data["code"], "NEX-COM-001")

    def test_add_rejects_invalid_roles(self):
        CompanyRole.objects.create(code="auditor")
        response = self.client.post(
            self.members_url,
            {"user_id": str(self.candidate.id), "role": "auditor"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "NEX-COM-001")
        self.assertIn("role", response.data["errors"])

    def test_owner_can_change_another_members_role(self):
        response = self.client.patch(
            self.member_url,
            {"role": "owner"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], "owner")
        self.assertEqual(
            CompanyMember.objects.get(company=self.company, user=self.member).role.code,
            "owner",
        )

    def test_changing_to_the_current_role_succeeds_without_changing_it(self):
        membership = CompanyMember.objects.get(company=self.company, user=self.member)
        current_role = membership.role

        response = self.client.patch(
            self.member_url,
            {"role": "member"},
            format="json",
        )

        membership.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(membership.role, current_role)

    def test_owner_cannot_change_own_role(self):
        response = self.client.patch(
            f"{self.members_url}{self.owner.id}/",
            {"role": "member"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_role_change_rejects_unknown_roles_and_unassociated_users(self):
        invalid_role = self.client.patch(
            self.member_url,
            {"role": "auditor"},
            format="json",
        )
        missing_member = self.client.patch(
            f"{self.members_url}{self.candidate.id}/",
            {"role": "member"},
            format="json",
        )

        self.assertEqual(invalid_role.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid_role.data["code"], "NEX-COM-001")
        self.assertEqual(missing_member.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_remove_member_without_deleting_user_or_other_memberships(self):
        response = self.client.delete(self.member_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(User.objects.filter(pk=self.member.id).exists())
        self.assertFalse(
            CompanyMember.objects.filter(company=self.company, user=self.member).exists()
        )
        self.assertTrue(
            CompanyMember.objects.filter(
                company=self.other_company,
                user=self.member,
                role__code="owner",
            ).exists()
        )

    def test_last_owner_cannot_be_removed(self):
        CompanyMember.objects.filter(
            company=self.company,
            user=self.second_owner,
        ).delete()

        response = self.client.delete(f"{self.members_url}{self.owner.id}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "NEX-COM-001")
        self.assertTrue(
            CompanyMember.objects.filter(company=self.company, user=self.owner).exists()
        )

    def test_removing_unassociated_user_returns_not_found(self):
        response = self.client.delete(f"{self.members_url}{self.candidate.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_foreign_company_is_hidden_from_member_operations(self):
        self.client.force_authenticate(user=self.candidate)

        response = self.client.get(self.members_url)
        add = self.client.post(
            self.members_url,
            {"user_id": str(self.candidate.id), "role": "member"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(add.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_cannot_add_change_or_remove_members(self):
        self.client.force_authenticate(user=self.member)

        adding = self.client.post(
            self.members_url,
            {"user_id": str(self.candidate.id), "role": "member"},
            format="json",
        )
        changing = self.client.patch(
            self.member_url,
            {"role": "owner"},
            format="json",
        )
        removing = self.client.delete(self.member_url)

        self.assertEqual(adding.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(changing.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(removing.status_code, status.HTTP_403_FORBIDDEN)

    def test_inactive_company_allows_member_list_but_rejects_changes(self):
        self.company.is_active = False
        self.company.save()

        listing = self.client.get(self.members_url)
        adding = self.client.post(
            self.members_url,
            {"user_id": str(self.candidate.id), "role": "member"},
            format="json",
        )
        changing = self.client.patch(
            self.member_url,
            {"role": "owner"},
            format="json",
        )
        removing = self.client.delete(self.member_url)

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(adding.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(changing.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(removing.status_code, status.HTTP_403_FORBIDDEN)
