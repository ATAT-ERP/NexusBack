import uuid
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.db import DatabaseError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from storage3.exceptions import StorageApiError

from apps.company.models import Company, CompanyMember, CompanyRole
from apps.documents.models import Document
from apps.users.models import User


class DocumentTests(APITestCase):
    url = "/api/documents/"
    usage_url = "/api/documents/usage/"

    def setUp(self):
        self.user = User.objects.create(id=uuid.uuid4(), email="member@example.com")
        self.owner_role = CompanyRole.objects.get(code="owner")
        self.client.force_authenticate(user=self.user)

    def create_document(self, company_id, **overrides):
        company, _ = Company.objects.get_or_create(
            id=company_id,
            defaults={"name": "Compa\u00f1\u00eda de prueba"},
        )
        CompanyMember.objects.get_or_create(
            user=self.user,
            company=company,
            defaults={"role": self.owner_role},
        )
        defaults = {
            "name": "Documento",
            "original_name": "documento.pdf",
            "storage_key": "documents/internal-key",
            "mime_type": "application/pdf",
            "size": 1024,
        }
        defaults.update(overrides)
        return Document.objects.create(company_id=company_id, **defaults)

    def detail_url(self, document_id, company_id=None):
        url = f"{self.url}{document_id}/"
        if company_id is not None:
            return f"{url}?company_id={company_id}"
        return url

    def get_usage(self, company_id=None):
        if company_id is None:
            return self.client.get(self.usage_url)
        return self.client.get(self.usage_url, {"company_id": company_id})

    def assert_validation_error(self, response, field):
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "NEX-DOC-001")
        self.assertEqual(response.data["message"], "Los datos enviados no son válidos.")
        self.assertIn(field, response.data["errors"])

    def assert_document_not_found(self, response):
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data,
            {"code": "NEX-DOC-002", "message": "Documento no encontrado."},
        )

    def test_lists_only_documents_for_requested_company(self):
        company_id = uuid.uuid4()
        document = self.create_document(company_id)
        self.create_document(uuid.uuid4())

        response = self.client.get(self.url, {"company_id": company_id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [str(document.id)])

    def test_search_does_not_mix_documents_from_other_companies(self):
        company_id = uuid.uuid4()
        document = self.create_document(company_id, name="Informe mensual")
        self.create_document(uuid.uuid4(), name="Informe confidencial")

        response = self.client.get(
            self.url,
            {"company_id": company_id, "q": "informe"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [str(document.id)])

    def test_searches_partially_by_name(self):
        company_id = uuid.uuid4()
        document = self.create_document(company_id, name="Informe mensual")

        response = self.client.get(
            self.url,
            {"company_id": company_id, "q": "mens"},
        )

        self.assertEqual([item["id"] for item in response.data], [str(document.id)])

    def test_searches_partially_by_original_name(self):
        company_id = uuid.uuid4()
        document = self.create_document(
            company_id,
            original_name="informe_agosto.pdf",
        )

        response = self.client.get(
            self.url,
            {"company_id": company_id, "q": "agosto"},
        )

        self.assertEqual([item["id"] for item in response.data], [str(document.id)])

    def test_search_is_case_insensitive_and_trims_whitespace(self):
        company_id = uuid.uuid4()
        document = self.create_document(company_id, name="INFORME STOCK")

        response = self.client.get(
            self.url,
            {"company_id": company_id, "q": "  informe  "},
        )

        self.assertEqual([item["id"] for item in response.data], [str(document.id)])

    def test_ignores_an_empty_search_term(self):
        company_id = uuid.uuid4()
        first_document = self.create_document(company_id)
        second_document = self.create_document(company_id)

        response = self.client.get(
            self.url,
            {"company_id": company_id, "q": "   "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            [item["id"] for item in response.data],
            [str(first_document.id), str(second_document.id)],
        )

    def test_filters_by_category(self):
        company_id = uuid.uuid4()
        category_id = uuid.uuid4()
        document = self.create_document(company_id, category_id=category_id)
        self.create_document(company_id, category_id=uuid.uuid4())

        response = self.client.get(
            self.url,
            {"company_id": company_id, "category_id": category_id},
        )

        self.assertEqual([item["id"] for item in response.data], [str(document.id)])

    def test_combines_search_and_category_filters(self):
        company_id = uuid.uuid4()
        category_id = uuid.uuid4()
        document = self.create_document(
            company_id,
            name="Informe mensual",
            category_id=category_id,
        )
        self.create_document(company_id, name="Informe anual", category_id=uuid.uuid4())
        self.create_document(company_id, name="Factura mensual", category_id=category_id)

        response = self.client.get(
            self.url,
            {
                "company_id": company_id,
                "category_id": category_id,
                "q": "informe",
            },
        )

        self.assertEqual([item["id"] for item in response.data], [str(document.id)])

    def test_returns_an_empty_collection_when_no_documents_match(self):
        company_id = uuid.uuid4()
        company = Company.objects.create(
            id=company_id,
            name="Compañía sin documentos",
        )
        CompanyMember.objects.create(
            user=self.user,
            company=company,
            role=self.owner_role,
        )

        response = self.client.get(self.url, {"company_id": company_id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_rejects_a_user_who_is_not_a_company_member(self):
        company_id = uuid.uuid4()
        company = Company.objects.create(id=company_id, name="Compañía ajena")
        Document.objects.create(
            company=company,
            name="Confidencial",
            original_name="confidencial.pdf",
            storage_key="documents/confidencial",
            mime_type="application/pdf",
            size=1024,
        )

        response = self.client.get(self.url, {"company_id": company_id})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_requires_company_id(self):
        response = self.client.get(self.url)

        self.assert_validation_error(response, "company_id")

    def test_rejects_invalid_uuids(self):
        response = self.client.get(self.url, {"company_id": "not-a-uuid"})

        self.assert_validation_error(response, "company_id")

        response = self.client.get(
            self.url,
            {"company_id": uuid.uuid4(), "category_id": "not-a-uuid"},
        )

        self.assert_validation_error(response, "category_id")

    def test_orders_documents_by_created_at_descending(self):
        company_id = uuid.uuid4()
        older = self.create_document(company_id, name="Anterior")
        newer = self.create_document(company_id, name="Reciente")
        now = timezone.now()
        Document.objects.filter(pk=older.pk).update(created_at=now - timedelta(days=1))
        Document.objects.filter(pk=newer.pk).update(created_at=now)

        response = self.client.get(self.url, {"company_id": company_id})

        self.assertEqual(
            [item["id"] for item in response.data],
            [str(newer.id), str(older.id)],
        )

    def test_does_not_expose_storage_key(self):
        company_id = uuid.uuid4()
        self.create_document(company_id, storage_key="documents/private-key")

        response = self.client.get(self.url, {"company_id": company_id})

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("storage_key", response.data[0])

    def test_renames_a_document(self):
        company_id = uuid.uuid4()
        document = self.create_document(company_id)

        response = self.client.patch(
            self.detail_url(document.id, company_id),
            {"name": "Informe agosto"},
            format="json",
        )

        document.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(document.name, "Informe agosto")
        self.assertEqual(response.data["name"], "Informe agosto")

    def test_trims_a_document_name(self):
        company_id = uuid.uuid4()
        document = self.create_document(company_id)

        response = self.client.patch(
            self.detail_url(document.id, company_id),
            {"name": "  Informe agosto  "},
            format="json",
        )

        document.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(document.name, "Informe agosto")

    def test_rejects_an_empty_document_name(self):
        company_id = uuid.uuid4()
        document = self.create_document(company_id)

        response = self.client.patch(
            self.detail_url(document.id, company_id),
            {"name": ""},
            format="json",
        )

        self.assert_validation_error(response, "name")

    def test_rejects_a_blank_document_name(self):
        company_id = uuid.uuid4()
        document = self.create_document(company_id)

        response = self.client.patch(
            self.detail_url(document.id, company_id),
            {"name": "   "},
            format="json",
        )

        self.assert_validation_error(response, "name")

    def test_updates_a_category(self):
        company_id = uuid.uuid4()
        document = self.create_document(company_id)
        category_id = uuid.uuid4()

        response = self.client.patch(
            self.detail_url(document.id, company_id),
            {"category_id": category_id},
            format="json",
        )

        document.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(document.category_id, category_id)

    def test_removes_a_category(self):
        company_id = uuid.uuid4()
        document = self.create_document(company_id, category_id=uuid.uuid4())

        response = self.client.patch(
            self.detail_url(document.id, company_id),
            {"category_id": None},
            format="json",
        )

        document.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(document.category_id)

    def test_updates_name_and_category(self):
        company_id = uuid.uuid4()
        document = self.create_document(company_id)
        category_id = uuid.uuid4()

        response = self.client.patch(
            self.detail_url(document.id, company_id),
            {"name": "Informe agosto", "category_id": category_id},
            format="json",
        )

        document.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(document.name, "Informe agosto")
        self.assertEqual(document.category_id, category_id)

    def test_patch_updates_only_the_sent_field(self):
        company_id = uuid.uuid4()
        category_id = uuid.uuid4()
        document = self.create_document(company_id, category_id=category_id)

        response = self.client.patch(
            self.detail_url(document.id, company_id),
            {"name": "Informe agosto"},
            format="json",
        )

        document.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(document.category_id, category_id)

    def test_patch_requires_company_id(self):
        document = self.create_document(uuid.uuid4())

        response = self.client.patch(
            self.detail_url(document.id),
            {"name": "Informe agosto"},
            format="json",
        )

        self.assert_validation_error(response, "company_id")

    def test_patch_rejects_an_invalid_company_id(self):
        document = self.create_document(uuid.uuid4())

        response = self.client.patch(
            self.detail_url(document.id, "not-a-uuid"),
            {"name": "Informe agosto"},
            format="json",
        )

        self.assert_validation_error(response, "company_id")

    def test_patch_rejects_an_invalid_category_id(self):
        company_id = uuid.uuid4()
        document = self.create_document(company_id)

        response = self.client.patch(
            self.detail_url(document.id, company_id),
            {"category_id": "not-a-uuid"},
            format="json",
        )

        self.assert_validation_error(response, "category_id")

    def test_patch_returns_not_found_for_an_unknown_document(self):
        response = self.client.patch(
            self.detail_url(uuid.uuid4(), uuid.uuid4()),
            {"name": "Informe agosto"},
            format="json",
        )

        self.assert_document_not_found(response)

    def test_patch_returns_not_found_for_an_invalid_document_id(self):
        response = self.client.patch(
            self.detail_url("not-a-uuid", uuid.uuid4()),
            {"name": "Informe agosto"},
            format="json",
        )

        self.assert_document_not_found(response)

    def test_patch_cannot_update_a_document_from_another_company(self):
        document = self.create_document(uuid.uuid4())

        response = self.client.patch(
            self.detail_url(document.id, uuid.uuid4()),
            {"name": "Informe agosto"},
            format="json",
        )

        document.refresh_from_db()
        self.assert_document_not_found(response)
        self.assertEqual(document.name, "Documento")

    def test_patch_does_not_expose_storage_key(self):
        company_id = uuid.uuid4()
        document = self.create_document(company_id)

        response = self.client.patch(
            self.detail_url(document.id, company_id),
            {"name": "Informe agosto"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("storage_key", response.data)

    def test_patch_ignores_read_only_fields(self):
        company_id = uuid.uuid4()
        document = self.create_document(company_id)
        original_name = document.original_name
        storage_key = document.storage_key
        mime_type = document.mime_type
        size = document.size

        response = self.client.patch(
            self.detail_url(document.id, company_id),
            {
                "name": "Informe agosto",
                "company_id": uuid.uuid4(),
                "original_name": "otro.pdf",
                "storage_key": "documents/other-key",
                "mime_type": "text/plain",
                "size": 2048,
            },
            format="json",
        )

        document.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(document.company_id, company_id)
        self.assertEqual(document.original_name, original_name)
        self.assertEqual(document.storage_key, storage_key)
        self.assertEqual(document.mime_type, mime_type)
        self.assertEqual(document.size, size)

    def test_usage_is_zero_without_documents(self):
        response = self.get_usage(uuid.uuid4())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["used"], 0)

    def test_usage_has_full_available_space_without_documents(self):
        response = self.get_usage(uuid.uuid4())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["available"], settings.DOCUMENT_COMPANY_LIMIT_BYTES)

    def test_usage_sums_one_document(self):
        company_id = uuid.uuid4()
        self.create_document(company_id, size=1024)

        response = self.get_usage(company_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["used"], 1024)

    def test_usage_sums_documents_for_the_same_company(self):
        company_id = uuid.uuid4()
        self.create_document(company_id, size=1024)
        self.create_document(company_id, size=2048)

        response = self.get_usage(company_id)

        self.assertEqual(response.data["used"], 3072)

    def test_usage_ignores_documents_from_other_companies(self):
        company_id = uuid.uuid4()
        self.create_document(company_id, size=1024)
        self.create_document(uuid.uuid4(), size=2048)

        response = self.get_usage(company_id)

        self.assertEqual(response.data["used"], 1024)

    @override_settings(DOCUMENT_COMPANY_LIMIT_BYTES=100)
    def test_usage_returns_the_configured_limit(self):
        response = self.get_usage(uuid.uuid4())

        self.assertEqual(response.data["limit"], 100)

    @override_settings(DOCUMENT_COMPANY_LIMIT_BYTES=100)
    def test_usage_calculates_available_space(self):
        company_id = uuid.uuid4()
        self.create_document(company_id, size=40)

        response = self.get_usage(company_id)

        self.assertEqual(response.data["available"], 60)

    @override_settings(DOCUMENT_COMPANY_LIMIT_BYTES=100)
    def test_usage_never_returns_negative_available_space(self):
        company_id = uuid.uuid4()
        self.create_document(company_id, size=101)

        response = self.get_usage(company_id)

        self.assertEqual(response.data["available"], 0)

    def test_usage_requires_company_id(self):
        response = self.get_usage()

        self.assert_validation_error(response, "company_id")

    def test_usage_rejects_an_invalid_company_id(self):
        response = self.get_usage("not-a-uuid")

        self.assert_validation_error(response, "company_id")

    def test_usage_allows_a_company_without_a_record(self):
        response = self.get_usage(uuid.uuid4())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["used"], 0)

    def test_usage_returns_only_public_fields(self):
        response = self.get_usage(uuid.uuid4())

        self.assertEqual(set(response.data), {"used", "limit", "available"})

    def test_usage_does_not_expose_the_safe_limit(self):
        response = self.get_usage(uuid.uuid4())

        self.assertNotIn("safe_limit", response.data)
        self.assertNotIn("DOCUMENT_STORAGE_SAFE_LIMIT_BYTES", response.data)


class DocumentListAuthenticationTests(APITestCase):
    url = "/api/documents/"

    def test_requires_authentication(self):
        response = self.client.get(self.url, {"company_id": uuid.uuid4()})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DocumentCreateTests(APITestCase):
    url = "/api/documents/"

    def setUp(self):
        self.user = User.objects.create(id=uuid.uuid4(), email="creator@example.com")
        self.company = Company.objects.create(name="Compañía de prueba")
        self.client.force_authenticate(user=self.user)

    def assert_validation_error(self, response, field):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "NEX-DOC-001")
        self.assertIn(field, response.data["errors"])

    @patch("apps.documents.api.views.storage_client")
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
        document = Document.objects.get(pk=response.data["id"])
        self.assertEqual(document.company, self.company)
        self.assertEqual(document.name, "informe.pdf")
        self.assertEqual(document.original_name, "informe.pdf")
        self.assertEqual(document.mime_type, "application/pdf")
        self.assertEqual(document.size, len(b"contenido del informe"))
        self.assertEqual(document.category_id, category_id)
        self.assertEqual(document.storage_key, f"{self.company.id}/{document.id}")
        self.assertNotIn("storage_key", response.data)
        storage_client.storage.from_.assert_called_once_with("documents")
        storage_client.storage.from_().upload.assert_called_once_with(
            document.storage_key,
            b"contenido del informe",
            {"content-type": "application/pdf"},
        )

    @patch("apps.documents.api.views.storage_client")
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

    @patch("apps.documents.api.views.storage_client")
    def test_requires_a_file(self, storage_client):
        response = self.client.post(
            self.url,
            {"company_id": self.company.id},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "NEX-DOC-001")
        self.assertIn("file", response.data["errors"])
        self.assertFalse(Document.objects.exists())
        storage_client.storage.from_.assert_not_called()

    @patch("apps.documents.api.views.storage_client")
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

    @patch("apps.documents.api.views.storage_client")
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

    @patch("apps.documents.api.views.storage_client")
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

    @patch("apps.documents.api.views.storage_client")
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

    @patch("apps.documents.api.views.storage_client")
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

    @patch("apps.documents.api.serializers.DocumentCreateSerializer.create", side_effect=DatabaseError)
    @patch("apps.documents.api.views.storage_client")
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

    @patch("apps.documents.api.views.storage_client")
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
        self.assertFalse(Document.objects.exists())
        storage_client.storage.from_().remove.assert_not_called()


class DocumentCreateAuthenticationTests(APITestCase):
    url = "/api/documents/"

    def setUp(self):
        self.company = Company.objects.create(name="Compañía de prueba")

    def test_requires_authentication(self):
        uploaded_file = SimpleUploadedFile("informe.pdf", b"contenido")

        response = self.client.post(
            self.url,
            {"company_id": self.company.id, "file": uploaded_file},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Document.objects.exists())
