import uuid

from rest_framework import status


from apps.cloud.files.tests.base import FileTestBase


class FileMetadataTests(FileTestBase):
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

    def test_delete_is_not_an_exposed_file_operation(self):
        document = self.create_document(uuid.uuid4())

        response = self.client.delete(self.detail_url(document.id, document.company_id))

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

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
