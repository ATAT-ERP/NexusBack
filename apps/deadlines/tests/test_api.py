import uuid
from datetime import date

from rest_framework import status
from rest_framework.test import APITestCase

from apps.company.models import Company, CompanyMember, CompanyRole
from apps.deadlines.models import Deadline
from apps.users.models import User


class DeadlineAPITests(APITestCase):
    url = "/api/deadlines/"

    def setUp(self):
        """Prepara usuarios, compañías y tareas compartiendo una compañía. @version 1.0"""
        self.user = User.objects.create(id=uuid.uuid4())
        self.other = User.objects.create(id=uuid.uuid4())
        self.company = Company.objects.create(name="Compartida")
        self.second = Company.objects.create(name="Otra autorizada")
        self.foreign = Company.objects.create(name="Ajena")
        role = CompanyRole.objects.get(code="member")
        for user, company in ((self.user, self.company), (self.user, self.second),
                              (self.other, self.company), (self.other, self.foreign)):
            CompanyMember.objects.create(user=user, company=company, role=role)
        self.deadline = Deadline.objects.create(
            owner=self.user, company=self.company, name="Propia", due_date=date(2026, 11, 1)
        )
        self.other_deadline = Deadline.objects.create(
            owner=self.other, company=self.company, name="Ajena", due_date=date(2026, 11, 2)
        )
        self.detail = f"{self.url}{self.deadline.id}/"

    def test_authentication_required_for_all_operations(self):
        """Exige autenticación para colección y detalle. @version 1.0"""
        for method, url in (("get", self.url), ("post", self.url), ("get", self.detail),
                            ("put", self.detail), ("patch", self.detail), ("delete", self.detail)):
            with self.subTest(method=method, url=url):
                self.assertEqual(getattr(self.client, method)(url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_crud_and_owner_is_read_only(self):
        """Permite CRUD propio sin aceptar un propietario del cliente. @version 1.0"""
        self.client.force_authenticate(self.user)
        response = self.client.post(self.url, {
            "company": str(self.second.id), "name": "IVA", "due_date": "2026-12-01",
            "owner": str(self.other.id), "period": "2026-11", "notes": "Nota",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        deadline = Deadline.objects.get(pk=response.data["id"])
        self.assertEqual(deadline.owner, self.user)
        self.assertEqual(response.data["status"], "pending")
        url = f"{self.url}{deadline.id}/"
        self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)
        response = self.client.put(url, {
            "company": str(self.company.id), "name": "Ganancias", "due_date": "2026-12-02",
            "owner": str(self.other.id),
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        deadline.refresh_from_db()
        self.assertEqual(deadline.owner, self.user)
        self.assertEqual(deadline.company, self.company)
        for value in ("completed", "pending"):
            response = self.client.patch(url, {"status": value}, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["status"], value)
        self.assertEqual(self.client.patch(url, {"status": "overdue"}, format="json").status_code, 400)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Deadline.objects.filter(pk=deadline.pk).exists())

    def test_company_and_required_fields_are_validated(self):
        """Rechaza compañías ajenas o inactivas y campos obligatorios ausentes. @version 1.0"""
        self.client.force_authenticate(self.user)
        data = {"name": "Tarea", "due_date": "2026-12-01"}
        for payload in (data, {**data, "company": str(self.foreign.id)},
                        {"company": str(self.company.id)},):
            self.assertEqual(self.client.post(self.url, payload, format="json").status_code, 400)
        self.second.is_active = False
        self.second.save()
        self.assertEqual(self.client.post(self.url, {**data, "company": str(self.second.id)}, format="json").status_code, 400)
        for company in (self.foreign, self.second):
            self.assertEqual(self.client.patch(self.detail, {"company": str(company.id)}, format="json").status_code, 400)
        self.deadline.refresh_from_db()
        self.assertEqual(self.deadline.company, self.company)

    def test_private_tasks_are_not_visible_to_other_members(self):
        """Oculta tareas ajenas aun si los usuarios comparten la compañía. @version 1.0"""
        self.client.force_authenticate(self.user)
        response = self.client.get(self.url)
        self.assertEqual([item["id"] for item in response.data], [str(self.deadline.id)])
        url = f"{self.url}{self.other_deadline.id}/"
        for method in ("get", "put", "patch", "delete"):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)(url, {}, format="json").status_code, 404)
        self.assertTrue(Deadline.objects.filter(pk=self.other_deadline.pk).exists())

    def test_inactive_company_preserves_read_only_access(self):
        """Conserva lectura histórica y rechaza todas las escrituras. @version 1.0"""
        self.client.force_authenticate(self.user)
        self.company.is_active = False
        self.company.save()
        self.assertEqual(len(self.client.get(self.url).data), 1)
        self.assertEqual(self.client.get(self.detail).status_code, 200)
        for method in ("put", "patch", "delete"):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)(self.detail, {"company": str(self.second.id)}, format="json").status_code, 403)
        self.assertTrue(Deadline.objects.filter(pk=self.deadline.pk).exists())

    def test_revoked_membership_removes_all_access(self):
        """Oculta la tarea propia cuando se revoca la membresía. @version 1.0"""
        self.client.force_authenticate(self.user)
        CompanyMember.objects.filter(user=self.user, company=self.company).delete()
        self.assertEqual(self.client.get(self.url).data, [])
        for method in ("get", "put", "patch", "delete"):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)(self.detail, {}, format="json").status_code, 404)
        self.assertEqual(self.client.post(self.url, {
            "company": str(self.company.id), "name": "Tarea", "due_date": "2026-12-01"
        }, format="json").status_code, 400)

    def test_bearer_authentication_is_used(self):
        """Autentica el listado con Bearer y rechaza tokens inválidos. @version 1.0"""
        from types import SimpleNamespace
        from unittest.mock import patch

        identity = SimpleNamespace(id=self.user.id, email=self.user.email)
        with patch(
            "apps.users.authentication.supabase.auth.get_user",
            return_value=SimpleNamespace(user=identity),
        ) as get_user:
            response = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer valid-token")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [str(self.deadline.id)])
        get_user.assert_called_once_with("valid-token")

        with patch("apps.users.authentication.supabase.auth.get_user", side_effect=ValueError):
            response = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer invalid-token")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_global_list_includes_only_owned_tasks_with_current_memberships(self):
        """Lista tareas propias de varias compañías, incluso inactivas. @version 1.0"""
        self.client.force_authenticate(self.user)
        second_deadline = Deadline.objects.create(
            owner=self.user, company=self.second, name="Segunda", due_date=date(2026, 12, 1)
        )
        inactive = Company.objects.create(name="Histórica", is_active=False)
        role = CompanyRole.objects.get(code="member")
        CompanyMember.objects.create(user=self.user, company=inactive, role=role)
        historical = Deadline.objects.create(
            owner=self.user, company=inactive, name="Histórica", due_date=date(2026, 10, 1)
        )
        revoked = Company.objects.create(name="Revocada")
        revoked_deadline = Deadline.objects.create(
            owner=self.user, company=revoked, name="Sin acceso", due_date=date(2026, 10, 1)
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item["id"] for item in response.data},
            {str(self.deadline.id), str(second_deadline.id), str(historical.id)},
        )
        self.assertNotIn(str(revoked_deadline.id), {item["id"] for item in response.data})

    def test_company_change_obeys_membership_for_patch_and_put(self):
        """Permite mover a otra compañía autorizada y rechaza destinos ajenos. @version 1.0"""
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            self.detail, {"company": str(self.second.id), "owner": str(self.other.id)}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.deadline.refresh_from_db()
        self.assertEqual(self.deadline.company, self.second)
        self.assertEqual(self.deadline.owner, self.user)

        response = self.client.put(self.detail, {
            "company": str(self.foreign.id), "name": "Editada", "due_date": "2026-12-01"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.deadline.refresh_from_db()
        self.assertEqual(self.deadline.company, self.second)
        self.assertEqual(self.deadline.name, "Propia")

        CompanyMember.objects.filter(user=self.user, company=self.second).delete()
        response = self.client.patch(self.detail, {"company": str(self.company.id)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.deadline.refresh_from_db()
        self.assertEqual(self.deadline.company, self.second)
