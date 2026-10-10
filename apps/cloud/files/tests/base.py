import uuid

from rest_framework.test import APITestCase

from apps.company.models import Company, CompanyMember, CompanyRole
from apps.cloud.models import File
from apps.users.models import User


class FileTestBase(APITestCase):
    url = "/api/cloud/files/"
    usage_url = "/api/cloud/files/usage/"

    def setUp(self):
        self.user = User.objects.create(id=uuid.uuid4(), email="member@example.com")
        self.owner_role = CompanyRole.objects.get(code="owner")
        self.client.force_authenticate(user=self.user)

    def create_company(self, company_id=None, **overrides):
        defaults = {"name": "Compañía de prueba"}
        defaults.update(overrides)
        if company_id is not None:
            defaults["id"] = company_id
        company = Company.objects.create(**defaults)
        CompanyMember.objects.get_or_create(
            user=self.user,
            company=company,
            defaults={"role": self.owner_role},
        )
        return company

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
        return File.objects.create(company_id=company_id, **defaults)

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
