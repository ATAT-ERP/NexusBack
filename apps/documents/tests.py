import uuid
from datetime import timedelta

from django.conf import settings
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.documents.models import Document


class DocumentTests(APITestCase):
    url = "/api/documents/"
    usage_url = "/api/documents/usage/"

    def create_document(self, company_id, **overrides):
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
        response = self.client.get(self.url, {"company_id": uuid.uuid4()})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

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
