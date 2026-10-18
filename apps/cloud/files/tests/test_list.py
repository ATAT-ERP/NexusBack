import uuid
from datetime import timedelta

from django.utils import timezone

from apps.company.models import Company, CompanyMember
from apps.cloud.models import File


from apps.cloud.files.tests.base import FileTestBase


class FileListTests(FileTestBase):
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
        File.objects.filter(pk=older.pk).update(created_at=now - timedelta(days=1))
        File.objects.filter(pk=newer.pk).update(created_at=now)

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
