"""Pruebas de autenticación y sincronización con Supabase Auth."""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import User


class SupabaseAuthenticationAPITests(APITestCase):
    def setUp(self):
        self.auth_user = SimpleNamespace(
            id=uuid.uuid4(),
            email="supabase@example.com",
        )

    def test_valid_supabase_identity_without_local_profile_is_synchronized(self):
        with patch(
            "apps.users.authentication.supabase.auth.get_user",
            return_value=SimpleNamespace(user=self.auth_user),
        ):
            response = self.client.get(
                "/api/users/me/",
                HTTP_AUTHORIZATION="Bearer valid-token",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.auth_user.id))
        self.assertEqual(response.data["email"], self.auth_user.email)
        local_user = User.objects.get(pk=self.auth_user.id)
        self.assertTrue(local_user.is_active)
        self.assertFalse(local_user.is_system_admin)

    def test_inactive_local_profile_is_rejected_even_with_valid_supabase_token(self):
        User.objects.create(
            id=self.auth_user.id,
            email=self.auth_user.email,
            is_active=False,
        )
        with patch(
            "apps.users.authentication.supabase.auth.get_user",
            return_value=SimpleNamespace(user=self.auth_user),
        ):
            response = self.client.get(
                "/api/users/me/",
                HTTP_AUTHORIZATION="Bearer valid-token",
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "NEX-USR-002")

    def test_verified_email_conflict_does_not_link_identity_to_another_user(self):
        User.objects.create(id=uuid.uuid4(), email=self.auth_user.email)
        with patch(
            "apps.users.authentication.supabase.auth.get_user",
            return_value=SimpleNamespace(user=self.auth_user),
        ):
            response = self.client.get(
                "/api/users/me/",
                HTTP_AUTHORIZATION="Bearer valid-token",
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(pk=self.auth_user.id).exists())

    def test_login_synchronizes_supabase_identity_and_returns_its_uuid(self):
        session = SimpleNamespace(
            access_token="access-token",
            refresh_token="refresh-token",
            token_type="bearer",
            expires_in=3600,
        )
        with patch(
            "apps.users.authentication.login",
            return_value=SimpleNamespace(user=self.auth_user, session=session),
        ):
            response = self.client.post(
                "/api/users/login/",
                {"email": self.auth_user.email, "password": "password"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.auth_user.id))
        local_user = User.objects.get(pk=self.auth_user.id)
        self.assertTrue(local_user.is_active)
        self.assertFalse(local_user.is_system_admin)

    def test_login_rejects_inactive_local_profile(self):
        User.objects.create(
            id=self.auth_user.id,
            email=self.auth_user.email,
            is_active=False,
        )
        session = SimpleNamespace(
            access_token="access-token",
            refresh_token="refresh-token",
            token_type="bearer",
            expires_in=3600,
        )
        with patch(
            "apps.users.authentication.login",
            return_value=SimpleNamespace(user=self.auth_user, session=session),
        ):
            response = self.client.post(
                "/api/users/login/",
                {"email": self.auth_user.email, "password": "password"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "NEX-USR-002")

    def test_registration_creates_profile_from_supabase_identity(self):
        with patch(
            "apps.users.authentication.register",
            return_value=SimpleNamespace(user=self.auth_user),
        ):
            response = self.client.post(
                "/api/users/register/",
                {"email": self.auth_user.email, "password": "password"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["id"], str(self.auth_user.id))
        self.assertTrue(User.objects.filter(pk=self.auth_user.id).exists())
