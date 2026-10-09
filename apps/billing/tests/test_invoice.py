import uuid
from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from apps.billing.enums import VATCondition
from apps.billing.enums.invoice import (
    DocumentType,
    InvoiceConcept,
    InvoiceStatus,
    InvoiceType,
)
from apps.billing.models import FiscalProfile, Invoice
from apps.billing.services.numbering import assign_point_of_sale_number
from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


class InvoiceAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Empresa facturas")
        self.fiscal_profile = FiscalProfile.objects.create(
            company=self.company,
            vat_condition=VATCondition.REGISTERED_RESPONSIBLE,
        )
        self.point_of_sale = assign_point_of_sale_number(self.fiscal_profile)
        self.user = User.objects.create(id=uuid.uuid4(), email="invoice@example.com")
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=CompanyRole.objects.get(code="owner"),
        )
        self.client.force_authenticate(user=self.user)
        self.list_url = f"/api/billing/companies/{self.company.id}/invoices/"

        self.other_company = Company.objects.create(name="Empresa ajena")
        other_profile = FiscalProfile.objects.create(
            company=self.other_company,
            vat_condition=VATCondition.MONOTAX,
        )
        self.other_point_of_sale = assign_point_of_sale_number(other_profile)

    def payload(self, **overrides):
        data = {
            "point_of_sale": self.point_of_sale.id,
            "invoice_type": InvoiceType.INVOICE_B,
            "concept": InvoiceConcept.PRODUCTS,
            "receiver_name": "Cliente Ejemplo",
            "receiver_vat_condition": VATCondition.FINAL_CONSUMER,
            "receiver_document_type": DocumentType.DNI,
            "receiver_document_number": "12345678",
            "receiver_address": "Av. Ejemplo 123",
        }
        data.update(overrides)
        return data

    def create_invoice(self, **overrides):
        data = self.payload(**overrides)
        return Invoice.objects.create(
            point_of_sale_id=data.pop("point_of_sale"), **data
        )

    def test_create_invoice_is_draft(self):
        response = self.client.post(self.list_url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        invoice = Invoice.objects.get(pk=response.data["id"])
        self.assertEqual(response.data["status"], "draft")
        self.assertEqual(invoice.status, InvoiceStatus.DRAFT)
        self.assertIsNone(invoice.number)
        self.assertIsNone(invoice.issue_date)

    def test_invoice_is_associated_with_point_of_sale(self):
        response = self.client.post(self.list_url, self.payload(), format="json")

        invoice = Invoice.objects.get(pk=response.data["id"])
        self.assertEqual(invoice.point_of_sale, self.point_of_sale)
        self.assertIn(invoice, self.point_of_sale.invoices.all())

    def test_create_rejects_point_of_sale_from_other_company(self):
        response = self.client.post(
            self.list_url,
            self.payload(point_of_sale=self.other_point_of_sale.id),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("point_of_sale", response.data)
        self.assertFalse(Invoice.objects.exists())

    def test_update_rejects_point_of_sale_from_other_company(self):
        invoice = self.create_invoice()

        response = self.client.patch(
            f"{self.list_url}{invoice.id}/",
            {"point_of_sale": self.other_point_of_sale.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        invoice.refresh_from_db()
        self.assertEqual(invoice.point_of_sale, self.point_of_sale)

    def test_enums_are_stored_with_fiscal_codes(self):
        response = self.client.post(
            self.list_url,
            self.payload(
                invoice_type=InvoiceType.INVOICE_A,
                concept=InvoiceConcept.PRODUCTS_AND_SERVICES,
                receiver_vat_condition=VATCondition.REGISTERED_RESPONSIBLE,
                receiver_document_type=DocumentType.CUIT,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        invoice = Invoice.objects.get(pk=response.data["id"])
        self.assertEqual(invoice.invoice_type, 1)
        self.assertEqual(invoice.concept, 3)
        self.assertEqual(invoice.receiver_vat_condition, 1)
        self.assertEqual(invoice.receiver_document_type, 80)
        self.assertEqual(invoice.status, "draft")

    def test_enums_reject_unknown_values(self):
        for field, value in (
            ("concept", 9),
            ("receiver_document_type", 99),
            ("receiver_vat_condition", 99),
            ("invoice_type", 2),
        ):
            with self.subTest(field=field):
                response = self.client.post(
                    self.list_url, self.payload(**{field: value}), format="json"
                )

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)

    def test_receiver_data_is_saved(self):
        response = self.client.post(self.list_url, self.payload(), format="json")

        invoice = Invoice.objects.get(pk=response.data["id"])
        self.assertEqual(invoice.receiver_name, "Cliente Ejemplo")
        self.assertEqual(invoice.receiver_vat_condition, VATCondition.FINAL_CONSUMER)
        self.assertEqual(invoice.receiver_document_type, DocumentType.DNI)
        self.assertEqual(invoice.receiver_document_number, "12345678")
        self.assertEqual(invoice.receiver_address, "Av. Ejemplo 123")

    def test_issuer_snapshot_is_ignored_on_create(self):
        response = self.client.post(
            self.list_url,
            self.payload(
                issuer_legal_name="Emisor Falso",
                issuer_tax_id="20000000001",
                issuer_address="Calle Falsa 123",
                issuer_vat_condition=VATCondition.MONOTAX,
                issuer_gross_income="123",
                issuer_activity_start_date="2020-01-01",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        invoice = Invoice.objects.get(pk=response.data["id"])
        self.assertIsNone(invoice.issuer_legal_name)
        self.assertIsNone(invoice.issuer_tax_id)
        self.assertIsNone(invoice.issuer_address)
        self.assertIsNone(invoice.issuer_vat_condition)
        self.assertIsNone(invoice.issuer_gross_income)
        self.assertIsNone(invoice.issuer_activity_start_date)

    def test_issuer_snapshot_is_ignored_on_update(self):
        invoice = self.create_invoice(
            issuer_legal_name="Emisor Original",
            issuer_tax_id="20000000001",
        )

        response = self.client.patch(
            f"{self.list_url}{invoice.id}/",
            {"issuer_legal_name": "Emisor Falso", "issuer_tax_id": "27000000002"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invoice.refresh_from_db()
        self.assertEqual(invoice.issuer_legal_name, "Emisor Original")
        self.assertEqual(invoice.issuer_tax_id, "20000000001")

    def test_totals_are_ignored_on_create(self):
        response = self.client.post(
            self.list_url,
            self.payload(
                net_taxed="100.00",
                net_untaxed="10.00",
                net_exempt="5.00",
                vat_amount="21.00",
                total="136.00",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        invoice = Invoice.objects.get(pk=response.data["id"])
        for field in ("net_taxed", "net_untaxed", "net_exempt", "vat_amount", "total"):
            with self.subTest(field=field):
                self.assertEqual(getattr(invoice, field), Decimal("0"))

    def test_totals_are_ignored_on_update(self):
        invoice = self.create_invoice()

        response = self.client.patch(
            f"{self.list_url}{invoice.id}/",
            {"total": "999.00", "vat_amount": "174.00"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invoice.refresh_from_db()
        self.assertEqual(invoice.total, Decimal("0"))
        self.assertEqual(invoice.vat_amount, Decimal("0"))

    def test_status_and_number_are_ignored(self):
        response = self.client.post(
            self.list_url,
            self.payload(status="issued", number=5, issue_date="2026-01-01"),
            format="json",
        )

        invoice = Invoice.objects.get(pk=response.data["id"])
        self.assertEqual(invoice.status, InvoiceStatus.DRAFT)
        self.assertIsNone(invoice.number)
        self.assertIsNone(invoice.issue_date)
