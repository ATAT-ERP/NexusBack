import uuid
from unittest.mock import patch

from django.conf import settings
from django.db import DatabaseError
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase
from storage3.exceptions import StorageApiError

from apps.company.models import Company, CompanyMember, CompanyRole
from apps.cloud.models import File
from apps.users.models import User


class FileCreateTests(APITestCase):
    url = "/api/cloud/files/"

    def setUp(self):
        self.user = User.objects.create(id=uuid.uuid4(), email="creator@example.com")
        self.company = Company.objects.create(name="Compañía de prueba")
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=CompanyRole.objects.get(code="owner"),
        )
        self.client.force_authenticate(user=self.user)

    def assert_validation_error(self, response, field):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "NEX-DOC-001")
        self.assertIn(field, response.data["errors"])

    def test_rejects_an_invalid_company_uuid_as_validation_error(self):
        uploaded_file = SimpleUploadedFile(
            "informe.pdf", b"contenido", content_type="application/pdf"
        )

        response = self.client.post(
            self.url,
            {"company_id": "not-a-uuid", "file": uploaded_file},
            format="multipart",
        )

        self.assert_validation_error(response, "company_id")

    def test_requires_company_id_for_upload(self):
        uploaded_file = SimpleUploadedFile(
            "informe.pdf", b"contenido", content_type="application/pdf"
        )

        response = self.client.post(
            self.url,
            {"file": uploaded_file},
            format="multipart",
        )

        self.assert_validation_error(response, "company_id")

    @patch("apps.cloud.files.api.views.storage_client")
    def test_creates_a_document_and_uploads_its_file(self, storage_client):
        uploaded_file = SimpleUploadedFile(
            "informe.pdf",
            b"contenido del informe",
            content_type="application/pdf",
        )
        category_id = uuid.uuid4()

        response = self.client.post(
            self.url,
            {
                "company_id": self.company.id,
                "file": uploaded_file,
                "category_id": category_id,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        document = File.objects.get(pk=response.data["id"])
        self.assertEqual(document.company, self.company)
        self.assertEqual(document.name, "informe.pdf")
        self.assertEqual(document.original_name, "informe.pdf")
        self.assertEqual(document.mime_type, "application/pdf")
        self.assertEqual(document.size, len(b"contenido del informe"))
        self.assertEqual(document.category_id, category_id)
        self.assertEqual(document.storage_key, f"{self.company.id}/{document.id}")
        self.assertNotIn("storage_key", response.data)
        storage_client.storage.from_.assert_any_call("documents")
        storage_client.storage.from_().upload.assert_called_once_with(
            document.storage_key,
            b"contenido del informe",
            {"content-type": "application/pdf"},
        )

    @patch("apps.cloud.files.api.views.storage_client")
    def test_uses_the_provided_name(self, storage_client):
        uploaded_file = SimpleUploadedFile(
            "informe.pdf",
            b"contenido",
            content_type="application/pdf",
        )

        response = self.client.post(
            self.url,
            {
                "company_id": self.company.id,
                "file": uploaded_file,
                "name": "Informe de agosto",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Informe de agosto")
        storage_client.storage.from_().upload.assert_called_once()

    @patch("apps.cloud.files.api.views.storage_client")
    def test_member_can_upload_to_an_authorized_company(self, storage_client):
        member = User.objects.create(id=uuid.uuid4(), email="member@example.com")
        CompanyMember.objects.create(
            user=member,
            company=self.company,
            role=CompanyRole.objects.get(code="member"),
        )
        self.client.force_authenticate(user=member)
        uploaded_file = SimpleUploadedFile(
            "informe.pdf", b"contenido", content_type="application/pdf"
        )

        response = self.client.post(
            self.url,
            {"company_id": self.company.id, "file": uploaded_file},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        storage_client.storage.from_().upload.assert_called_once()

    @patch("apps.cloud.files.api.views.storage_client")
    def test_rejects_upload_to_a_company_without_membership(self, storage_client):
        company = Company.objects.create(name="Compañía ajena")
        uploaded_file = SimpleUploadedFile(
            "informe.pdf", b"contenido", content_type="application/pdf"
        )

        response = self.client.post(
            self.url,
            {"company_id": company.id, "file": uploaded_file},
            format="multipart",
        )

        missing = self.client.post(
            self.url,
            {
                "company_id": uuid.uuid4(),
                "file": SimpleUploadedFile(
                    "informe.pdf", b"contenido", content_type="application/pdf"
                ),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data,
            {"code": "NEX-DOC-002", "message": "Documento no encontrado."},
        )
        self.assertEqual(response.data, missing.data)
        self.assertFalse(File.objects.exists())
        storage_client.storage.from_.assert_not_called()

    @patch("apps.cloud.files.api.views.storage_client")
    def test_rejects_upload_to_an_inactive_company(self, storage_client):
        self.company.is_active = False
        self.company.save(update_fields=["is_active"])
        uploaded_file = SimpleUploadedFile(
            "informe.pdf", b"contenido", content_type="application/pdf"
        )

        response = self.client.post(
            self.url,
            {"company_id": self.company.id, "file": uploaded_file},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(File.objects.exists())
        storage_client.storage.from_.assert_not_called()

    def test_rejects_metadata_updates_for_an_inactive_company(self):
        self.company.is_active = False
        self.company.save(update_fields=["is_active"])
        document = File.objects.create(
            company=self.company,
            name="Informe",
            original_name="informe.pdf",
            storage_key="documents/informe",
            mime_type="application/pdf",
            size=10,
        )

        response = self.client.patch(
            f"{self.url}{document.id}/?company_id={self.company.id}",
            {"name": "Editado"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        document.refresh_from_db()
        self.assertEqual(document.name, "Informe")

    @patch("apps.cloud.files.api.views.storage_client")
    def test_requires_a_file(self, storage_client):
        response = self.client.post(
            self.url,
            {"company_id": self.company.id},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "NEX-DOC-001")
        self.assertIn("file", response.data["errors"])
        self.assertFalse(File.objects.exists())
        storage_client.storage.from_.assert_not_called()

    @patch("apps.cloud.files.api.views.storage_client")
    def test_rejects_an_empty_file(self, storage_client):
        uploaded_file = SimpleUploadedFile(
            "vacio.pdf",
            b"",
            content_type="application/pdf",
        )

        response = self.client.post(
            self.url,
            {"company_id": self.company.id, "file": uploaded_file},
            format="multipart",
        )

        self.assert_validation_error(response, "file")
        storage_client.storage.from_.assert_not_called()

    @patch("apps.cloud.files.api.views.storage_client")
    def test_accepts_a_file_of_exactly_six_megabytes(self, storage_client):
        self.assertEqual(settings.DOCUMENT_MAX_SIZE_BYTES, 6 * 1024 * 1024)
        uploaded_file = SimpleUploadedFile(
            "limite.pdf",
            b"a" * settings.DOCUMENT_MAX_SIZE_BYTES,
            content_type="application/pdf",
        )

        response = self.client.post(
            self.url,
            {"company_id": self.company.id, "file": uploaded_file},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        storage_client.storage.from_().upload.assert_called_once()

    @patch("apps.cloud.files.api.views.storage_client")
    def test_rejects_a_file_larger_than_six_megabytes(self, storage_client):
        uploaded_file = SimpleUploadedFile(
            "grande.pdf",
            b"a" * (settings.DOCUMENT_MAX_SIZE_BYTES + 1),
            content_type="application/pdf",
        )

        response = self.client.post(
            self.url,
            {"company_id": self.company.id, "file": uploaded_file},
            format="multipart",
        )

        self.assert_validation_error(response, "file")
        storage_client.storage.from_.assert_not_called()

    @patch("apps.cloud.files.api.views.storage_client")
    def test_accepts_the_allowed_mime_types(self, storage_client):
        mime_types = (
            "application/pdf",
            "image/jpeg",
            "image/png",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        for mime_type in mime_types:
            with self.subTest(mime_type=mime_type):
                uploaded_file = SimpleUploadedFile(
                    "archivo",
                    b"contenido",
                    content_type=mime_type,
                )

                response = self.client.post(
                    self.url,
                    {"company_id": self.company.id, "file": uploaded_file},
                    format="multipart",
                )

                self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(storage_client.storage.from_().upload.call_count, len(mime_types))

    @patch("apps.cloud.files.api.views.storage_client")
    def test_rejects_a_disallowed_mime_type(self, storage_client):
        uploaded_file = SimpleUploadedFile(
            "archivo.txt",
            b"contenido",
            content_type="text/plain",
        )

        response = self.client.post(
            self.url,
            {"company_id": self.company.id, "file": uploaded_file},
            format="multipart",
        )

        self.assert_validation_error(response, "file")
        storage_client.storage.from_.assert_not_called()

    @patch("apps.cloud.files.api.serializers.FileCreateSerializer.create", side_effect=DatabaseError)
    @patch("apps.cloud.files.api.views.storage_client")
    def test_removes_the_uploaded_file_when_metadata_save_fails(
        self,
        storage_client,
        create,
    ):
        uploaded_file = SimpleUploadedFile(
            "informe.pdf",
            b"contenido",
            content_type="application/pdf",
        )

        with self.assertRaises(DatabaseError):
            self.client.post(
                self.url,
                {"company_id": self.company.id, "file": uploaded_file},
                format="multipart",
            )

        storage_key = storage_client.storage.from_().upload.call_args.args[0]
        storage_client.storage.from_().remove.assert_called_once_with([storage_key])

    @patch("apps.cloud.files.api.views.storage_client")
    def test_does_not_save_metadata_when_upload_fails(self, storage_client):
        storage_client.storage.from_().upload.side_effect = StorageApiError(
            "Storage unavailable",
            "InternalError",
            500,
        )
        uploaded_file = SimpleUploadedFile(
            "informe.pdf",
            b"contenido",
            content_type="application/pdf",
        )

        response = self.client.post(
            self.url,
            {"company_id": self.company.id, "file": uploaded_file},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(response.data["code"], "NEX-DOC-003")
        self.assertFalse(File.objects.exists())
        storage_client.storage.from_().remove.assert_not_called()
