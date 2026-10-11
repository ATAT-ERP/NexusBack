import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.billing.enums.invoice import (
    DocumentType,
    InvoiceConcept,
    InvoiceStatus,
    InvoiceType,
)
from apps.billing.enums.tax import TaxTreatment, VATCondition, VATRate
from apps.billing.models import FiscalProfile, Invoice, InvoiceItem, InvoiceSequence
from apps.billing.services.issuing import issue_invoice
from apps.billing.services.numbering import assign_point_of_sale_number
from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


class InvoiceFlowTestCase(APITestCase):
    RECEIVER_CUIT = "30000000007"  # CUIT con dígito verificador válido

    def setUp(self):
        self.company = Company.objects.create(
            name="Emisor",
            legal_name="Emisor S.A.",
            tax_id="20000000001",
            address_street="Av. Corrientes",
            address_number="1234",
            address_city="Buenos Aires",
            address_province="Buenos Aires",
        )
        self.fiscal_profile = FiscalProfile.objects.create(
            company=self.company,
            vat_condition=VATCondition.REGISTERED_RESPONSIBLE,
            gross_income="901-123456-7",
            business_start_date=date(2020, 1, 1),
        )
        self.point_of_sale = assign_point_of_sale_number(self.fiscal_profile)
        self.user = User.objects.create(id=uuid.uuid4(), email="issue@example.com")
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=CompanyRole.objects.get(code="owner"),
        )
        self.client.force_authenticate(user=self.user)
        self.base_url = f"/api/billing/companies/{self.company.id}/invoices/"

    def make_invoice(self, with_item=True, **overrides):
        data = {
            "point_of_sale": self.point_of_sale,
            "invoice_type": InvoiceType.INVOICE_B,
            "concept": InvoiceConcept.PRODUCTS,
            "receiver_name": "Cliente Ejemplo",
            "receiver_vat_condition": VATCondition.FINAL_CONSUMER,
            "receiver_document_type": DocumentType.DNI,
            "receiver_document_number": "12345678",
            "receiver_address": "Av. Ejemplo 123",
        }
        data.update(overrides)
        invoice = Invoice.objects.create(**data)
        if with_item:
            InvoiceItem.objects.create(
                invoice=invoice,
                description="Producto",
                quantity=Decimal("2"),
                unit_price=Decimal("100.00"),
                discount=Decimal("0"),
                tax_treatment=TaxTreatment.TAXED,
                vat_rate=VATRate.TWENTY_ONE,
            )
        return invoice

    def make_invoice_a(self, **overrides):
        return self.make_invoice(
            invoice_type=InvoiceType.INVOICE_A,
            receiver_vat_condition=VATCondition.REGISTERED_RESPONSIBLE,
            receiver_document_type=DocumentType.CUIT,
            receiver_document_number=self.RECEIVER_CUIT,
            **overrides,
        )

    def issue_url(self, invoice):
        return f"{self.base_url}{invoice.id}/issue/"

    def results(self, response):
        # Soporta que el listado esté paginado o no.
        data = response.data
        return data["results"] if isinstance(data, dict) else data


class InvoiceIssueTests(InvoiceFlowTestCase):
    def assert_not_issued(self, invoice):
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.DRAFT)
        self.assertIsNone(invoice.number)
        self.assertIsNone(invoice.issue_date)
        self.assertFalse(InvoiceSequence.objects.exists())

    def assert_issue_rejected(self, invoice, field):
        response = self.client.post(self.issue_url(invoice))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(field, response.data)
        self.assert_not_issued(invoice)

    def test_issue_invoice(self):
        invoice = self.make_invoice()

        response = self.client.post(self.issue_url(invoice))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "issued")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertEqual(invoice.issue_date, timezone.localdate())
        self.assertEqual(invoice.net_taxed, Decimal("200.00"))
        self.assertEqual(invoice.vat_amount, Decimal("42.00"))
        self.assertEqual(invoice.total, Decimal("242.00"))

    def test_first_number_is_one_and_formatted(self):
        invoice = self.make_invoice()

        response = self.client.post(self.issue_url(invoice))

        self.assertEqual(response.data["number"], 1)
        self.assertEqual(response.data["point_of_sale_number"], "00001")
        self.assertEqual(response.data["formatted_number"], "00001-00000001")

    def test_numbers_increment(self):
        first = self.make_invoice()
        second = self.make_invoice()

        self.client.post(self.issue_url(first))
        self.client.post(self.issue_url(second))

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.number, second.number), (1, 2))

    def test_sequences_are_independent_by_type_and_point_of_sale(self):
        other_point_of_sale = assign_point_of_sale_number(self.fiscal_profile)
        invoice_b = self.make_invoice()
        invoice_a = self.make_invoice_a()
        invoice_b_other_pos = self.make_invoice(point_of_sale=other_point_of_sale)

        for invoice in (invoice_b, invoice_a, invoice_b_other_pos):
            response = self.client.post(self.issue_url(invoice))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            invoice.refresh_from_db()
            self.assertEqual(invoice.number, 1)
        self.assertEqual(InvoiceSequence.objects.count(), 3)

    def test_issuer_snapshot_is_copied_and_frozen(self):
        invoice = self.make_invoice()

        self.client.post(self.issue_url(invoice))

        invoice.refresh_from_db()
        self.assertEqual(invoice.issuer_legal_name, "Emisor S.A.")
        self.assertEqual(invoice.issuer_tax_id, "20000000001")
        self.assertEqual(
            invoice.issuer_address, "Av. Corrientes 1234, Buenos Aires, Buenos Aires"
        )
        self.assertEqual(invoice.issuer_vat_condition, VATCondition.REGISTERED_RESPONSIBLE)
        self.assertEqual(invoice.issuer_gross_income, "901-123456-7")
        self.assertEqual(invoice.issuer_activity_start_date, date(2020, 1, 1))

        Company.objects.filter(pk=self.company.pk).update(legal_name="Nombre nuevo")
        invoice.refresh_from_db()
        self.assertEqual(invoice.issuer_legal_name, "Emisor S.A.")

    def test_failure_does_not_consume_sequence(self):
        invoice = self.make_invoice()

        with patch.object(Invoice, "save", side_effect=RuntimeError("fallo simulado")):
            with self.assertRaises(RuntimeError):
                issue_invoice(invoice)

        self.assert_not_issued(invoice)

        issue_invoice(invoice)
        invoice.refresh_from_db()
        self.assertEqual(invoice.number, 1)

    def test_cannot_issue_twice(self):
        invoice = self.make_invoice()
        self.client.post(self.issue_url(invoice))

        response = self.client.post(self.issue_url(invoice))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)
        invoice.refresh_from_db()
        self.assertEqual(invoice.number, 1)
        self.assertEqual(InvoiceSequence.objects.get().last_number, 1)

    def test_issued_invoice_cannot_be_modified(self):
        other_point_of_sale = assign_point_of_sale_number(self.fiscal_profile)
        invoice = self.make_invoice()
        self.client.post(self.issue_url(invoice))

        for payload in (
            {"receiver_name": "Otro receptor"},
            {"invoice_type": InvoiceType.INVOICE_A},
            {"concept": InvoiceConcept.SERVICES},
            {"point_of_sale": other_point_of_sale.id},
        ):
            with self.subTest(payload=payload):
                response = self.client.patch(
                    f"{self.base_url}{invoice.id}/", payload, format="json"
                )

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        invoice.refresh_from_db()
        self.assertEqual(invoice.receiver_name, "Cliente Ejemplo")
        self.assertEqual(invoice.invoice_type, InvoiceType.INVOICE_B)
        self.assertEqual(invoice.point_of_sale, self.point_of_sale)

    def test_rejects_invoice_without_items(self):
        self.assert_issue_rejected(self.make_invoice(with_item=False), "items")

    def test_rejects_inactive_point_of_sale(self):
        invoice = self.make_invoice()
        self.point_of_sale.is_active = False
        self.point_of_sale.save()

        self.assert_issue_rejected(invoice, "point_of_sale")

    def test_rejects_company_without_required_data(self):
        invoice = self.make_invoice()
        Company.objects.filter(pk=self.company.pk).update(legal_name=None)

        self.assert_issue_rejected(invoice, "company")

    def test_rejects_invalid_invoice_type_combination(self):
        invoice = self.make_invoice(invoice_type=InvoiceType.INVOICE_A)

        self.assert_issue_rejected(invoice, "invoice_type")

    def test_rejects_services_without_dates(self):
        invoice = self.make_invoice(concept=InvoiceConcept.SERVICES)

        self.assert_issue_rejected(invoice, "service_date_from")

    def test_rejects_invalid_item(self):
        invoice = self.make_invoice(with_item=False)
        InvoiceItem.objects.create(
            invoice=invoice,
            description="Cantidad inválida",
            quantity=Decimal("0"),
            unit_price=Decimal("10.00"),
            discount=Decimal("0"),
            tax_treatment=TaxTreatment.EXEMPT,
        )

        self.assert_issue_rejected(invoice, "quantity")

    def test_rejects_invalid_receiver_document(self):
        invoice = self.make_invoice(
            receiver_document_type=DocumentType.CUIT,
            receiver_document_number="20000000002",
        )

        self.assert_issue_rejected(invoice, "receiver_document_number")

    def test_rejects_due_date_before_issue_date(self):
        invoice = self.make_invoice(due_date=date(2000, 1, 1))

        self.assert_issue_rejected(invoice, "due_date")

    def test_user_without_membership_cannot_issue(self):
        invoice = self.make_invoice()
        stranger = User.objects.create(id=uuid.uuid4(), email="stranger@example.com")
        self.client.force_authenticate(user=stranger)

        response = self.client.post(self.issue_url(invoice))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assert_not_issued(invoice)

    def test_cannot_issue_invoice_of_other_company(self):
        other_company = Company.objects.create(name="Otra empresa")
        other_profile = FiscalProfile.objects.create(
            company=other_company,
            vat_condition=VATCondition.REGISTERED_RESPONSIBLE,
        )
        other_point_of_sale = assign_point_of_sale_number(other_profile)
        other_invoice = self.make_invoice(point_of_sale=other_point_of_sale)

        response = self.client.post(self.issue_url(other_invoice))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assert_not_issued(other_invoice)


class InvoiceQueryTests(InvoiceFlowTestCase):
    def setUp(self):
        super().setUp()
        self.invoice_1 = self.make_invoice(receiver_name="Alpha")
        self.invoice_2 = self.make_invoice(
            receiver_name="Beta", receiver_document_number="87654321"
        )
        self.invoice_3 = self.make_invoice_a(receiver_name="Gamma")  # queda en borrador
        issue_invoice(self.invoice_1)
        issue_invoice(self.invoice_2)
        Invoice.objects.filter(pk=self.invoice_1.pk).update(issue_date=date(2026, 1, 10))
        Invoice.objects.filter(pk=self.invoice_2.pk).update(issue_date=date(2026, 2, 10))

    def ids(self, params):
        response = self.client.get(self.base_url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {item["id"] for item in self.results(response)}

    def test_list_returns_company_invoices(self):
        other_company = Company.objects.create(name="Otra empresa")
        other_profile = FiscalProfile.objects.create(
            company=other_company,
            vat_condition=VATCondition.REGISTERED_RESPONSIBLE,
        )
        self.make_invoice(point_of_sale=assign_point_of_sale_number(other_profile))

        self.assertEqual(
            self.ids({}),
            {self.invoice_1.id, self.invoice_2.id, self.invoice_3.id},
        )

    def test_filters(self):
        other_point_of_sale = assign_point_of_sale_number(self.fiscal_profile)
        everything = {self.invoice_1.id, self.invoice_2.id, self.invoice_3.id}
        cases = (
            ({"status": "issued"}, {self.invoice_1.id, self.invoice_2.id}),
            ({"status": "draft"}, {self.invoice_3.id}),
            ({"invoice_type": InvoiceType.INVOICE_A.value}, {self.invoice_3.id}),
            (
                {"invoice_type": InvoiceType.INVOICE_B.value},
                {self.invoice_1.id, self.invoice_2.id},
            ),
            ({"point_of_sale": self.point_of_sale.id}, everything),
            ({"point_of_sale": other_point_of_sale.id}, set()),
            ({"issue_date_from": "2026-02-01"}, {self.invoice_2.id}),
            ({"issue_date_to": "2026-01-31"}, {self.invoice_1.id}),
            (
                {"issue_date_from": "2026-01-01", "issue_date_to": "2026-01-31"},
                {self.invoice_1.id},
            ),
            ({"receiver": "alp"}, {self.invoice_1.id}),
            ({"receiver": "87654"}, {self.invoice_2.id}),
            ({"number": "2"}, {self.invoice_2.id}),
            ({"number": "00001-00000001"}, {self.invoice_1.id}),
            ({"number": "00002-00000001"}, set()),
        )
        for params, expected in cases:
            with self.subTest(params=params):
                self.assertEqual(self.ids(params), expected)

    def test_invalid_filters_are_rejected(self):
        for params in ({"status": "desconocido"}, {"number": "abc"}, {"issue_date_from": "hoy"}):
            with self.subTest(params=params):
                response = self.client.get(self.base_url, params)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_detail_returns_contract_of_issued_invoice(self):
        response = self.client.get(f"{self.base_url}{self.invoice_1.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["point_of_sale_number"], "00001")
        self.assertEqual(data["formatted_number"], "00001-00000001")
        self.assertEqual(data["invoice_type_display"], "Factura B")
        self.assertEqual(data["concept_display"], "Productos")
        self.assertEqual(data["status"], "issued")
        self.assertEqual(data["receiver_name"], "Alpha")
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["total"], "242.00")
        self.assertEqual(data["issuer_legal_name"], "Emisor S.A.")

    def test_detail_of_draft_has_no_number_or_snapshot(self):
        response = self.client.get(f"{self.base_url}{self.invoice_3.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["formatted_number"])
        self.assertIsNone(response.data["issuer_legal_name"])

class InvoiceItemImmutabilityTests(InvoiceFlowTestCase):
    def item_payload(self, **overrides):
        data = {
            "description": "Ítem nuevo",
            "quantity": "1.00",
            "unit_price": "50.00",
            "discount": "0.00",
            "tax_treatment": TaxTreatment.TAXED,
            "vat_rate": VATRate.TWENTY_ONE.value,
        }
        data.update(overrides)
        return data

    def test_draft_items_can_still_be_managed(self):
        invoice = self.make_invoice()
        items_url = f"{self.base_url}{invoice.id}/items/"

        created = self.client.post(items_url, self.item_payload(), format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

        item_url = f"{items_url}{created.data['id']}/"
        updated = self.client.patch(item_url, {"description": "Editado"}, format="json")
        self.assertEqual(updated.status_code, status.HTTP_200_OK)

        deleted = self.client.delete(item_url)
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

    def test_issued_invoice_items_are_immutable(self):
        invoice = self.make_invoice()
        item = invoice.items.get()
        self.client.post(f"{self.base_url}{invoice.id}/issue/")
        items_url = f"{self.base_url}{invoice.id}/items/"
        item_url = f"{items_url}{item.id}/"

        responses = (
            self.client.post(items_url, self.item_payload(), format="json"),
            self.client.patch(item_url, {"unit_price": "1.00"}, format="json"),
            self.client.delete(item_url),
        )

        for response in responses:
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("status", response.data)
        self.assertEqual(invoice.items.count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.unit_price, Decimal("100.00"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.total, Decimal("242.00"))