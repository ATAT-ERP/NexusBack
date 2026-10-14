import uuid

from django.conf import settings
from django.test import override_settings


from apps.cloud.files.tests.base import FileTestBase


class FileUsageTests(FileTestBase):
    def test_usage_is_zero_without_documents(self):
        company = self.create_company()
        response = self.get_usage(company.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["used"], 0)

    def test_usage_has_full_available_space_without_documents(self):
        company = self.create_company()
        response = self.get_usage(company.id)

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
        company = self.create_company()
        response = self.get_usage(company.id)

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
        company = self.create_company()
        response = self.get_usage(company.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["used"], 0)

    def test_usage_returns_only_public_fields(self):
        company = self.create_company()
        response = self.get_usage(company.id)

        self.assertEqual(set(response.data), {"used", "limit", "available"})

    def test_usage_does_not_expose_the_safe_limit(self):
        company = self.create_company()
        response = self.get_usage(company.id)

        self.assertNotIn("safe_limit", response.data)
        self.assertNotIn("DOCUMENT_STORAGE_SAFE_LIMIT_BYTES", response.data)
