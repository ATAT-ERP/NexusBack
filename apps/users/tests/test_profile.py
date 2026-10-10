"""Pruebas de consulta, edición y permisos del perfil de usuario."""

import uuid

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.users.models import User


class UserProfileAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(
            id=uuid.uuid4(),
            email="persona@example.com",
            first_name="Ana",
            last_name="Pérez",
        )
        self.other_user = User.objects.create(
            id=uuid.uuid4(),
            email="otra@example.com",
            first_name="Otra",
            last_name="Persona",
        )
        self.me_url = "/api/users/me/"
        self.client.force_authenticate(user=self.user)

    def test_get_me_returns_authenticated_profile_identity_and_personal_data(self):
        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.user.id))
        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["first_name"], "Ana")
        self.assertEqual(response.data["last_name"], "Pérez")

    def test_patch_me_updates_only_submitted_personal_fields(self):
        response = self.client.patch(
            self.me_url,
            {"first_name": "María"},
            format="json",
        )

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "María")
        self.assertEqual(response.data["last_name"], "Pérez")
        self.assertEqual(self.user.last_name, "Pérez")

    def test_profile_writes_reject_protected_fields(self):
        protected_values = {
            "id": str(uuid.uuid4()),
            "email": "nuevo@example.com",
            "is_active": False,
            "is_system_admin": True,
            "avatar_path": "avatar.png",
        }
        for field, value in protected_values.items():
            with self.subTest(field=field):
                response = self.client.patch(
                    self.me_url,
                    {"first_name": "Intento", field: value},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Ana")
        self.assertEqual(self.user.email, "persona@example.com")
        self.assertTrue(self.user.is_active)
        self.assertFalse(self.user.is_system_admin)
        self.assertIsNone(self.user.avatar_path)

    def test_profile_writes_reject_unknown_fields(self):
        response = self.client.patch(
            self.me_url,
            {"phone": "+541100000000"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", response.data["errors"])

    def test_profile_requires_authentication(self):
        response = APIClient().get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_normal_user_cannot_read_or_update_another_profile(self):
        detail_url = f"/api/users/{self.other_user.id}/"

        read_response = self.client.get(detail_url)
        update_response = self.client.patch(
            detail_url,
            {"first_name": "Cambio"},
            format="json",
        )

        self.assertEqual(read_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)
        self.other_user.refresh_from_db()
        self.assertEqual(self.other_user.first_name, "Otra")

    def test_only_system_admin_can_list_and_search_users(self):
        self.assertEqual(
            self.client.get("/api/users/").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.get("/api/users/search/?q=persona").status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.user.is_system_admin = True
        self.user.save(update_fields=["is_system_admin"])
        self.assertEqual(
            self.client.get("/api/users/").status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.get("/api/users/search/?q=persona").status_code,
            status.HTTP_200_OK,
        )

    def test_only_system_admin_can_change_another_users_privileges(self):
        target_url = f"/api/users/{self.other_user.id}/"
        responses = [
            self.client.post(f"{target_url}activate/", {}, format="json"),
            self.client.post(f"{target_url}deactivate/", {}, format="json"),
            self.client.post(
                f"{target_url}system-admin/",
                {"is_system_admin": True},
                format="json",
            ),
        ]

        self.assertTrue(
            all(response.status_code == status.HTTP_403_FORBIDDEN for response in responses)
        )
        self.other_user.refresh_from_db()
        self.assertTrue(self.other_user.is_active)
        self.assertFalse(self.other_user.is_system_admin)
