import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.company.models import Company, CompanyMember, CompanyRole
from apps.cloud.models import File
from apps.users.models import User


from apps.cloud.files.tests.base import FileTestBase


class FileAccessTests(FileTestBase):
    def test_rejects_a_user_who_is_not_a_company_member(self):
        company_id = uuid.uuid4()
        company = Company.objects.create(id=company_id, name="Compañía ajena")
        File.objects.create(
            company=company,
            name="Confidencial",
            original_name="confidencial.pdf",
            storage_key="documents/confidencial",
            mime_type="application/pdf",
            size=1024,
        )

        response = self.client.get(self.url, {"company_id": company_id})

        missing = self.client.get(self.url, {"company_id": uuid.uuid4()})

        self.assert_document_not_found(response)
        self.assertEqual(response.data, missing.data)

    def test_member_can_list_documents_for_the_company(self):
        company_id = uuid.uuid4()
        document = self.create_document(company_id)
        member = User.objects.create(id=uuid.uuid4(), email="collaborator@example.com")
        CompanyMember.objects.create(
            user=member,
            company_id=company_id,
            role=CompanyRole.objects.get(code="member"),
        )
        self.client.force_authenticate(user=member)

        response = self.client.get(self.url, {"company_id": company_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [str(document.id)])

    def test_inactive_company_allows_historical_file_reads(self):
        company = self.create_company(is_active=False)
        document = File.objects.create(
            company=company,
            name="Histórico",
            original_name="historico.pdf",
            storage_key="documents/historico",
            mime_type="application/pdf",
            size=1024,
        )

        listing = self.client.get(self.url, {"company_id": company.id})
        usage = self.get_usage(company.id)

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in listing.data], [str(document.id)])
        self.assertEqual(usage.status_code, status.HTTP_200_OK)
        self.assertEqual(usage.data["used"], 1024)

    def test_usage_rejects_a_user_without_company_membership(self):
        company = Company.objects.create(name="Compañía ajena")

        response = self.get_usage(company.id)

        missing = self.get_usage(uuid.uuid4())

        self.assert_document_not_found(response)
        self.assertEqual(response.data, missing.data)

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

    def test_patch_denies_a_user_without_membership(self):
        company = Company.objects.create(name="Compañía ajena")
        document = File.objects.create(
            company=company,
            name="Confidencial",
            original_name="confidencial.pdf",
            storage_key="documents/confidencial",
            mime_type="application/pdf",
            size=100,
        )

        response = self.client.patch(
            self.detail_url(document.id, company.id),
            {"name": "Editado"},
            format="json",
        )

        missing = self.client.patch(
            self.detail_url(uuid.uuid4(), uuid.uuid4()),
            {"name": "Editado"},
            format="json",
        )
        self.assert_document_not_found(response)
        self.assertEqual(response.data, missing.data)
        document.refresh_from_db()
        self.assertEqual(document.name, "Confidencial")


class FileListAuthenticationTests(APITestCase):
    url = "/api/cloud/files/"

    def test_requires_authentication(self):
        response = self.client.get(self.url, {"company_id": uuid.uuid4()})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_metadata_update_requires_authentication(self):
        user = User.objects.create(id=uuid.uuid4(), email="owner@example.com")
        company = Company.objects.create(name="Compañía de prueba")
        CompanyMember.objects.create(
            user=user,
            company=company,
            role=CompanyRole.objects.get(code="owner"),
        )
        document = File.objects.create(
            company=company,
            name="Informe",
            original_name="informe.pdf",
            storage_key="documents/informe",
            mime_type="application/pdf",
            size=10,
        )

        response = self.client.patch(
            f"{self.url}{document.id}/?company_id={company.id}",
            {"name": "Editado"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class FileCreateAuthenticationTests(APITestCase):
    url = "/api/cloud/files/"

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
        self.assertFalse(File.objects.exists())
