import uuid
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.billing.enums import VATCondition
from apps.billing.enums.invoice import DocumentType, InvoiceConcept, InvoiceType
from apps.billing.enums.tax import TaxTreatment, VATRate
from apps.billing.models import FiscalProfile, Invoice, InvoiceItem
from apps.billing.services.numbering import assign_point_of_sale_number
from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


def create_invoice(point_of_sale):
    return Invoice.objects.create(
        point_of_sale=point_of_sale,
        invoice_type=InvoiceType.INVOICE_B,
        concept=InvoiceConcept.PRODUCTS,
        receiver_name="Cliente Ejemplo",
        receiver_vat_condition=VATCondition.FINAL_CONSUMER,
        receiver_document_type=DocumentType.DNI,
        receiver_document_number="12345678",
        receiver_address="Av. Ejemplo 123",
    )


class InvoiceItemModelTests(TestCase):
    def setUp(self):
        company = Company.objects.create(name="Empresa ítems")
        fiscal_profile = FiscalProfile.objects.create(
            company=company,
            vat_condition=VATCondition.REGISTERED_RESPONSIBLE,
        )
        self.invoice = create_invoice(assign_point_of_sale_number(fiscal_profile))

    def create_item(self, **overrides):
        data = {
            "invoice": self.invoice,
            "description": "Producto",
            "quantity": Decimal("2.00"),
            "unit_price": Decimal("100.00"),
            "tax_treatment": TaxTreatment.TAXED,
            "vat_rate": VATRate.TWENTY_ONE,
        }
        data.update(overrides)
        return InvoiceItem.objects.create(**data)

    def test_decimal_fields_are_stored_as_decimal(self):
        self.create_item(discount=Decimal("10.50"))

        item = InvoiceItem.objects.get()
        self.assertEqual(item.quantity, Decimal("2.00"))
        self.assertEqual(item.unit_price, Decimal("100.00"))
        self.assertEqual(item.discount, Decimal("10.50"))
        for field in ("quantity", "unit_price", "discount"):
            self.assertIsInstance(getattr(item, field), Decimal)

    def test_discount_defaults_to_zero(self):
        item = self.create_item()

        self.assertEqual(InvoiceItem.objects.get(pk=item.pk).discount, Decimal("0"))

    def test_discount_accepts_limits(self):
        self.create_item(discount=Decimal("0.00"))
        self.create_item(discount=Decimal("100.00"))

        self.assertEqual(InvoiceItem.objects.count(), 2)

    def test_discount_above_100_violates_constraint(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_item(discount=Decimal("100.01"))

    def test_discount_below_0_violates_constraint(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_item(discount=Decimal("-0.01"))

    def test_vat_rate_is_optional(self):
        item = self.create_item(tax_treatment=TaxTreatment.EXEMPT, vat_rate=None)

        self.assertIsNone(InvoiceItem.objects.get(pk=item.pk).vat_rate)

    def test_enums_use_expected_values(self):
        self.assertEqual(
            [value for value, _ in TaxTreatment.choices],
            ["taxed", "exempt", "untaxed", "not_discriminated"],
        )
        self.assertEqual(
            {label: value for value, label in VATRate.choices},
            {"0%": 3, "2,5%": 9, "5%": 8, "10,5%": 4, "21%": 5, "27%": 6},
        )

    def test_deleting_invoice_deletes_its_items(self):
        self.create_item()

        self.invoice.delete()

        self.assertFalse(InvoiceItem.objects.exists())


class InvoiceItemAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Empresa ítems API")
        fiscal_profile = FiscalProfile.objects.create(
            company=self.company,
            vat_condition=VATCondition.REGISTERED_RESPONSIBLE,
        )
        point_of_sale = assign_point_of_sale_number(fiscal_profile)
        self.invoice = create_invoice(point_of_sale)
        self.other_invoice = create_invoice(point_of_sale)
        self.user = User.objects.create(id=uuid.uuid4(), email="items@example.com")
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=CompanyRole.objects.get(code="owner"),
        )
        self.client.force_authenticate(user=self.user)
        self.list_url = (
            f"/api/billing/companies/{self.company.id}/invoices/"
            f"{self.invoice.id}/items/"
        )

    def payload(self, **overrides):
        data = {
            "description": "Producto",
            "quantity": "2.00",
            "unit_price": "100.00",
            "discount": "10.00",
            "tax_treatment": TaxTreatment.TAXED,
            "vat_rate": VATRate.TWENTY_ONE,
        }
        data.update(overrides)
        return data

    def create_item(self):
        return InvoiceItem.objects.create(
            invoice=self.invoice,
            description="Producto",
            quantity=Decimal("2.00"),
            unit_price=Decimal("100.00"),
            tax_treatment=TaxTreatment.TAXED,
            vat_rate=VATRate.TWENTY_ONE,
        )

    def test_create_item(self):
        response = self.client.post(self.list_url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        item = InvoiceItem.objects.get(pk=response.data["id"])
        self.assertEqual(item.invoice, self.invoice)
        self.assertEqual(item.description, "Producto")
        self.assertEqual(item.tax_treatment, "taxed")
        self.assertEqual(item.vat_rate, 5)

    def test_decimal_values_are_not_floats(self):
        response = self.client.post(self.list_url, self.payload(), format="json")

        item = InvoiceItem.objects.get(pk=response.data["id"])
        for field, expected in (
            ("quantity", Decimal("2.00")),
            ("unit_price", Decimal("100.00")),
            ("discount", Decimal("10.00")),
        ):
            with self.subTest(field=field):
                self.assertIsInstance(getattr(item, field), Decimal)
                self.assertEqual(getattr(item, field), expected)
                self.assertIsInstance(response.data[field], str)

    def test_invoice_comes_from_url_not_body(self):
        response = self.client.post(
            self.list_url,
            self.payload(invoice=self.other_invoice.id),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            InvoiceItem.objects.get(pk=response.data["id"]).invoice, self.invoice
        )

    def test_list_returns_only_items_of_the_invoice(self):
        self.create_item()
        InvoiceItem.objects.create(
            invoice=self.other_invoice,
            description="Otro",
            quantity=Decimal("1.00"),
            unit_price=Decimal("1.00"),
            tax_treatment=TaxTreatment.EXEMPT,
        )

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["description"], "Producto")

    def test_update_item(self):
        item = self.create_item()

        response = self.client.patch(
            f"{self.list_url}{item.id}/",
            {"description": "Editado", "quantity": "5.00", "discount": "25.50"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item.refresh_from_db()
        self.assertEqual(item.description, "Editado")
        self.assertEqual(item.quantity, Decimal("5.00"))
        self.assertEqual(item.discount, Decimal("25.50"))

    def test_delete_item(self):
        item = self.create_item()

        response = self.client.delete(f"{self.list_url}{item.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(InvoiceItem.objects.filter(pk=item.id).exists())

    def test_enums_are_stored_with_expected_values(self):
        response = self.client.post(
            self.list_url,
            self.payload(
                tax_treatment=TaxTreatment.NOT_DISCRIMINATED,
                vat_rate=VATRate.TEN_AND_HALF,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        item = InvoiceItem.objects.get(pk=response.data["id"])
        self.assertEqual(item.tax_treatment, "not_discriminated")
        self.assertEqual(item.vat_rate, 4)

    def test_vat_rate_can_be_omitted(self):
        data = self.payload(tax_treatment=TaxTreatment.EXEMPT)
        del data["vat_rate"]

        response = self.client.post(self.list_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(InvoiceItem.objects.get(pk=response.data["id"]).vat_rate)

    def test_enums_reject_unknown_values(self):
        for field, value in (("tax_treatment", "otro"), ("vat_rate", 99)):
            with self.subTest(field=field):
                response = self.client.post(
                    self.list_url, self.payload(**{field: value}), format="json"
                )

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)
