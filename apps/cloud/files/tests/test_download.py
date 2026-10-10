import uuid
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase
from storage3.exceptions import StorageApiError

from apps.company.models import Company, CompanyMember, CompanyRole
from apps.cloud.models import File
from apps.users.models import User


class FileDownloadTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(id=uuid.uuid4(), email="member@example.com")
        self.company = Company.objects.create(name="Compañía de prueba")
        owner_role = CompanyRole.objects.get(code="owner")
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=owner_role,
        )
        self.document = File.objects.create(
            company=self.company,
            name="Informe",
            original_name="informe.pdf",
            storage_key="documents/private-key",
            mime_type="application/pdf",
            size=1024,
        )
        self.url = f"/api/cloud/files/{self.document.id}/download/"

    @patch("apps.cloud.files.api.views.storage_client")
    def test_returns_a_signed_url_for_a_company_member(self, storage_client):
        self.client.force_authenticate(user=self.user)
        storage_client.storage.from_().create_signed_url.return_value = {
            "signedURL": "https://storage.example/signed-url"
        }

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"url": "https://storage.example/signed-url"})
        storage_client.storage.from_.assert_any_call("documents")
        storage_client.storage.from_().create_signed_url.assert_called_once_with(
            self.document.storage_key,
            60,
            {"download": self.document.original_name},
        )

    def test_requires_authentication(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("apps.cloud.files.api.views.storage_client")
    def test_inactive_company_allows_historical_download(self, storage_client):
        self.company.is_active = False
        self.company.save(update_fields=["is_active"])
        self.client.force_authenticate(user=self.user)
        storage_client.storage.from_().create_signed_url.return_value = {
            "signedURL": "https://storage.example/signed-url"
        }

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        storage_client.storage.from_().create_signed_url.assert_called_once()

    @patch("apps.cloud.files.api.views.storage_client")
    def test_rejects_a_user_who_is_not_a_company_member(self, storage_client):
        user = User.objects.create(id=uuid.uuid4(), email="other@example.com")
        self.client.force_authenticate(user=user)

        response = self.client.get(self.url)

        missing = self.client.get(f"/api/cloud/files/{uuid.uuid4()}/download/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data,
            {"code": "NEX-DOC-002", "message": "Documento no encontrado."},
        )
        self.assertEqual(response.data, missing.data)
        storage_client.storage.from_.assert_not_called()

    @patch("apps.cloud.files.api.views.storage_client")
    def test_returns_not_found_for_an_unknown_document(self, storage_client):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/cloud/files/{uuid.uuid4()}/download/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        storage_client.storage.from_.assert_not_called()

    @patch("apps.cloud.files.api.views.storage_client")
    def test_handles_storage_errors(self, storage_client):
        self.client.force_authenticate(user=self.user)
        storage_client.storage.from_().create_signed_url.side_effect = StorageApiError(
            "Storage unavailable",
            "InternalError",
            500,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(
            response.data,
            {
                "code": "NEX-DOC-004",
                "message": "No fue posible preparar la descarga del documento.",
            },
        )
        self.assertNotIn(self.document.storage_key, str(response.data))
