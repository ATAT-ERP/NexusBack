import uuid
from datetime import date
from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.billing.enums import CreditNoteType, VATCondition
from apps.billing.enums.invoice import (
    DocumentType,
    InvoiceConcept,
    InvoiceStatus,
    InvoiceType,
)
from apps.billing.enums.tax import TaxTreatment, VATRate
from apps.billing.models import (
    CreditNote,
    CreditNoteInvoice,
    CreditNoteItem,
    FiscalProfile,
    Invoice,
    InvoiceSequence,
)
from apps.billing.services.numbering import assign_point_of_sale_number
from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


def create_invoice(point_of_sale, **overrides):
    data = {
        "point_of_sale": point_of_sale,
        "invoice_type": InvoiceType.INVOICE_A,
        "status": InvoiceStatus.ISSUED,
        "concept": InvoiceConcept.PRODUCTS,
        "receiver_name": "Cliente Ejemplo",
        "receiver_vat_condition": VATCondition.REGISTERED_RESPONSIBLE,
        "receiver_document_type": DocumentType.CUIT,
        "receiver_document_number": "20123456786",
        "receiver_address": "Av. Ejemplo 123",
    }
    data.update(overrides)
    return Invoice.objects.create(**data)


class CreditNoteAPITestCase(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Empresa NC")
        fiscal_profile = FiscalProfile.objects.create(
            company=self.company,
            vat_condition=VATCondition.REGISTERED_RESPONSIBLE,
        )
        self.point_of_sale = assign_point_of_sale_number(fiscal_profile)
        self.user = User.objects.create(id=uuid.uuid4(), email="nc@example.com")
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=CompanyRole.objects.get(code="owner"),
        )
        self.client.force_authenticate(user=self.user)
        self.base_url = f"/api/billing/companies/{self.company.id}/credit-notes/"
        self.credit_note = CreditNote.objects.create(
            point_of_sale=self.point_of_sale,
            credit_note_type=CreditNoteType.CREDIT_NOTE_A,
        )
        self.invoices_url = f"{self.base_url}{self.credit_note.id}/invoices/"
        self.items_url = f"{self.base_url}{self.credit_note.id}/items/"

    def associate(self, *invoices):
        return self.client.post(
            self.invoices_url,
            {"invoices": [invoice.id for invoice in invoices]},
            format="json",
        )


class CreditNoteCreateTests(CreditNoteAPITestCase):
    def test_creates_empty_draft(self):
        response = self.client.post(
            self.base_url,
            {
                "point_of_sale": self.point_of_sale.id,
                "credit_note_type": CreditNoteType.CREDIT_NOTE_B,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], InvoiceStatus.DRAFT)
        self.assertEqual(response.data["credit_note_invoices"], [])

    def test_rejects_point_of_sale_of_another_company(self):
        other_point_of_sale = assign_point_of_sale_number(
            FiscalProfile.objects.create(
                company=Company.objects.create(name="Otra empresa NC"),
                vat_condition=VATCondition.REGISTERED_RESPONSIBLE,
            )
        )

        response = self.client.post(
            self.base_url,
            {
                "point_of_sale": other_point_of_sale.id,
                "credit_note_type": CreditNoteType.CREDIT_NOTE_A,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("point_of_sale", response.data)

    def test_non_member_cannot_access(self):
        outsider = User.objects.create(id=uuid.uuid4(), email="outsider-nc@example.com")
        self.client.force_authenticate(user=outsider)

        response = self.client.get(self.base_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CreditNoteInvoiceAssociationTests(CreditNoteAPITestCase):
    def test_association_is_cumulative(self):
        first = create_invoice(self.point_of_sale)
        second = create_invoice(self.point_of_sale)

        self.assertEqual(self.associate(first).status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.associate(second).status_code, status.HTTP_201_CREATED)

        response = self.client.get(self.invoices_url)
        self.assertEqual(
            {row["invoice"] for row in response.data}, {first.id, second.id}
        )

    def test_rejects_invoice_that_is_not_issued(self):
        draft = create_invoice(self.point_of_sale, status=InvoiceStatus.DRAFT)

        response = self.associate(draft)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(CreditNoteInvoice.objects.exists())

    def test_rejects_invoice_of_non_homologous_type(self):
        invoice = create_invoice(self.point_of_sale, invoice_type=InvoiceType.INVOICE_B)

        response = self.associate(invoice)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(CreditNoteInvoice.objects.exists())

    def test_rejects_invoice_already_associated(self):
        invoice = create_invoice(self.point_of_sale)
        self.associate(invoice)

        response = self.associate(invoice)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CreditNoteInvoice.objects.count(), 1)

    def test_rejects_different_receiver_and_associates_none(self):
        valid = create_invoice(self.point_of_sale)
        other_receiver = create_invoice(
            self.point_of_sale, receiver_document_number="30711234569"
        )

        response = self.associate(valid, other_receiver)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(CreditNoteInvoice.objects.exists())

    def test_rejects_receiver_different_from_already_associated(self):
        self.associate(create_invoice(self.point_of_sale))

        response = self.associate(
            create_invoice(self.point_of_sale, receiver_document_number="30711234569")
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CreditNoteInvoice.objects.count(), 1)

    def test_rejects_invoice_of_another_company(self):
        other_point_of_sale = assign_point_of_sale_number(
            FiscalProfile.objects.create(
                company=Company.objects.create(name="Otra empresa NC 2"),
                vat_condition=VATCondition.REGISTERED_RESPONSIBLE,
            )
        )

        response = self.associate(create_invoice(other_point_of_sale))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(CreditNoteInvoice.objects.exists())

    def test_rejects_association_when_credit_note_is_issued(self):
        CreditNote.objects.filter(pk=self.credit_note.pk).update(
            status=InvoiceStatus.ISSUED
        )

        response = self.associate(create_invoice(self.point_of_sale))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_disassociation_deletes_items_in_cascade(self):
        association = CreditNoteInvoice.objects.create(
            credit_note=self.credit_note, invoice=create_invoice(self.point_of_sale)
        )
        CreditNoteItem.objects.create(
            credit_note_invoice=association,
            description="Producto",
            quantity=1,
            unit_price=100,
            tax_treatment=TaxTreatment.TAXED,
            vat_rate=VATRate.TWENTY_ONE,
        )

        response = self.client.delete(f"{self.invoices_url}{association.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CreditNoteInvoice.objects.exists())
        self.assertFalse(CreditNoteItem.objects.exists())

    def test_cannot_disassociate_when_credit_note_is_issued(self):
        association = CreditNoteInvoice.objects.create(
            credit_note=self.credit_note, invoice=create_invoice(self.point_of_sale)
        )
        CreditNote.objects.filter(pk=self.credit_note.pk).update(
            status=InvoiceStatus.ISSUED
        )

        response = self.client.delete(f"{self.invoices_url}{association.id}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(CreditNoteInvoice.objects.exists())


class CreditNoteItemAPITests(CreditNoteAPITestCase):
    def setUp(self):
        super().setUp()
        self.association = CreditNoteInvoice.objects.create(
            credit_note=self.credit_note, invoice=create_invoice(self.point_of_sale)
        )

    def payload(self, **overrides):
        data = {
            "credit_note_invoice": self.association.id,
            "description": "Producto",
            "quantity": "1.00",
            "unit_price": "100.00",
            "tax_treatment": TaxTreatment.TAXED,
            "vat_rate": VATRate.TWENTY_ONE,
        }
        data.update(overrides)
        return data

    def test_creates_and_lists_item(self):
        response = self.client.post(self.items_url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        listing = self.client.get(self.items_url)
        self.assertEqual(len(listing.data), 1)

    def test_rejects_association_of_another_credit_note(self):
        other = CreditNote.objects.create(
            point_of_sale=self.point_of_sale,
            credit_note_type=CreditNoteType.CREDIT_NOTE_A,
        )
        foreign = CreditNoteInvoice.objects.create(
            credit_note=other, invoice=create_invoice(self.point_of_sale)
        )

        response = self.client.post(
            self.items_url,
            self.payload(credit_note_invoice=foreign.id),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(CreditNoteItem.objects.exists())

    def test_rejects_item_when_credit_note_is_issued(self):
        CreditNote.objects.filter(pk=self.credit_note.pk).update(
            status=InvoiceStatus.ISSUED
        )

        response = self.client.post(self.items_url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(CreditNoteItem.objects.exists())

    def test_updates_and_deletes_item_in_draft(self):
        item = CreditNoteItem.objects.create(
            credit_note_invoice=self.association,
            description="Producto",
            quantity=1,
            unit_price=100,
            tax_treatment=TaxTreatment.TAXED,
            vat_rate=VATRate.TWENTY_ONE,
        )
        detail_url = f"{self.items_url}{item.id}/"

        patch = self.client.patch(detail_url, {"description": "Editado"}, format="json")
        delete = self.client.delete(detail_url)

        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data["description"], "Editado")
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)


class CreditNoteIssueTests(APITestCase):
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
        fiscal_profile = FiscalProfile.objects.create(
            company=self.company,
            vat_condition=VATCondition.REGISTERED_RESPONSIBLE,
            gross_income="901-123456-7",
            business_start_date=date(2020, 1, 1),
        )
        self.point_of_sale = assign_point_of_sale_number(fiscal_profile)
        self.user = User.objects.create(id=uuid.uuid4(), email="nc-issue@example.com")
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=CompanyRole.objects.get(code="owner"),
        )
        self.client.force_authenticate(user=self.user)
        self.base_url = f"/api/billing/companies/{self.company.id}/credit-notes/"

    def make_credit_note(self, credit_note_type=CreditNoteType.CREDIT_NOTE_A):
        return CreditNote.objects.create(
            point_of_sale=self.point_of_sale, credit_note_type=credit_note_type
        )

    def add_invoice(self, credit_note, invoice, *unit_prices, **item_overrides):
        """Asocia la factura y le carga un ítem de cantidad 1 por cada precio."""
        association = CreditNoteInvoice.objects.create(
            credit_note=credit_note, invoice=invoice
        )
        item_data = {
            "tax_treatment": TaxTreatment.TAXED,
            "vat_rate": VATRate.TWENTY_ONE,
            **item_overrides,
        }
        for unit_price in unit_prices:
            CreditNoteItem.objects.create(
                credit_note_invoice=association,
                description="Producto",
                quantity=Decimal("1"),
                unit_price=Decimal(unit_price),
                **item_data,
            )
        return association

    def issue(self, credit_note):
        return self.client.post(f"{self.base_url}{credit_note.id}/issue/")

    def assert_rejected(self, credit_note, field):
        response = self.issue(credit_note)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(field, response.data)
        credit_note.refresh_from_db()
        self.assertEqual(credit_note.status, InvoiceStatus.DRAFT)
        self.assertIsNone(credit_note.number)
        self.assertFalse(InvoiceSequence.objects.exists())

    def test_issues_each_credit_note_type_with_its_own_sequence(self):
        cases = (
            (CreditNoteType.CREDIT_NOTE_A, InvoiceType.INVOICE_A, {}),
            (CreditNoteType.CREDIT_NOTE_B, InvoiceType.INVOICE_B, {}),
            (
                CreditNoteType.CREDIT_NOTE_C,
                InvoiceType.INVOICE_C,
                {"tax_treatment": TaxTreatment.NOT_DISCRIMINATED, "vat_rate": None},
            ),
        )
        for credit_note_type, invoice_type, item_overrides in cases:
            with self.subTest(credit_note_type=credit_note_type):
                credit_note = self.make_credit_note(credit_note_type)
                invoice = create_invoice(
                    self.point_of_sale,
                    invoice_type=invoice_type,
                    total=Decimal("121.00"),
                )
                self.add_invoice(credit_note, invoice, "100.00", **item_overrides)

                response = self.issue(credit_note)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["status"], InvoiceStatus.ISSUED)
                self.assertEqual(response.data["number"], 1)
        self.assertEqual(
            set(InvoiceSequence.objects.values_list("invoice_type", flat=True)),
            {3, 8, 13},
        )

    def test_issue_fixes_totals_snapshots_and_association_total(self):
        credit_note = self.make_credit_note()
        invoice = create_invoice(self.point_of_sale, total=Decimal("242.00"))
        association = self.add_invoice(credit_note, invoice, "100.00")

        response = self.issue(credit_note)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        credit_note.refresh_from_db()
        association.refresh_from_db()
        self.assertEqual(credit_note.net_taxed, Decimal("100.00"))
        self.assertEqual(credit_note.vat_amount, Decimal("21.00"))
        self.assertEqual(credit_note.total, Decimal("121.00"))
        self.assertEqual(association.total, Decimal("121.00"))
        self.assertEqual(credit_note.issue_date, timezone.localdate())
        self.assertEqual(credit_note.issuer_legal_name, "Emisor S.A.")
        self.assertEqual(credit_note.issuer_tax_id, "20000000001")
        self.assertEqual(credit_note.receiver_name, invoice.receiver_name)
        self.assertEqual(
            credit_note.receiver_document_number, invoice.receiver_document_number
        )

    def test_partial_credit_keeps_invoice_issued_until_balance_is_zero(self):
        invoice = create_invoice(self.point_of_sale, total=Decimal("242.00"))
        first = self.make_credit_note()
        self.add_invoice(first, invoice, "100.00")
        second = self.make_credit_note()
        self.add_invoice(second, invoice, "100.00")

        self.assertEqual(self.issue(first).status_code, status.HTTP_200_OK)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)

        self.assertEqual(self.issue(second).status_code, status.HTTP_200_OK)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.CANCELLED)

    def test_total_reversal_cancels_invoice(self):
        credit_note = self.make_credit_note()
        invoice = create_invoice(self.point_of_sale, total=Decimal("121.00"))
        self.add_invoice(credit_note, invoice, "100.00")

        self.issue(credit_note)

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.CANCELLED)

    def test_only_fully_credited_invoices_are_cancelled(self):
        credit_note = self.make_credit_note()
        covered = create_invoice(self.point_of_sale, total=Decimal("121.00"))
        partial = create_invoice(self.point_of_sale, total=Decimal("242.00"))
        self.add_invoice(credit_note, covered, "100.00")
        self.add_invoice(credit_note, partial, "100.00")

        response = self.issue(credit_note)

        self.assertEqual(response.data["total"], "242.00")
        covered.refresh_from_db()
        partial.refresh_from_db()
        self.assertEqual(covered.status, InvoiceStatus.CANCELLED)
        self.assertEqual(partial.status, InvoiceStatus.ISSUED)

    def test_rejects_credit_above_invoice_total(self):
        credit_note = self.make_credit_note()
        invoice = create_invoice(self.point_of_sale, total=Decimal("100.00"))
        self.add_invoice(credit_note, invoice, "100.00")

        self.assert_rejected(credit_note, "items")

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)

    def test_rejects_credit_above_balance_left_by_previous_credit_notes(self):
        invoice = create_invoice(self.point_of_sale, total=Decimal("242.00"))
        first = self.make_credit_note()
        self.add_invoice(first, invoice, "100.00")
        self.issue(first)
        second = self.make_credit_note()
        self.add_invoice(second, invoice, "100.00", "100.00")

        response = self.issue(second)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("saldo disponible (121.00)", str(response.data["items"]))
        second.refresh_from_db()
        self.assertEqual(second.status, InvoiceStatus.DRAFT)

    def test_draft_credit_notes_do_not_reduce_the_balance(self):
        invoice = create_invoice(self.point_of_sale, total=Decimal("121.00"))
        self.add_invoice(self.make_credit_note(), invoice, "100.00")
        credit_note = self.make_credit_note()
        self.add_invoice(credit_note, invoice, "100.00")

        self.assertEqual(self.issue(credit_note).status_code, status.HTTP_200_OK)

    def test_issued_credit_note_is_immutable(self):
        credit_note = self.make_credit_note()
        invoice = create_invoice(self.point_of_sale, total=Decimal("242.00"))
        association = self.add_invoice(credit_note, invoice, "100.00")
        self.issue(credit_note)
        item = association.items.get()
        url = f"{self.base_url}{credit_note.id}"

        responses = (
            self.issue(credit_note),
            self.client.post(
                f"{url}/invoices/",
                {"invoices": [create_invoice(self.point_of_sale).id]},
                format="json",
            ),
            self.client.delete(f"{url}/invoices/{association.id}/"),
            self.client.patch(
                f"{url}/items/{item.id}/", {"description": "Editado"}, format="json"
            ),
            self.client.delete(f"{url}/items/{item.id}/"),
        )

        for response in responses:
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CreditNoteItem.objects.count(), 1)
        self.assertEqual(CreditNoteInvoice.objects.count(), 1)

    def test_rejects_credit_note_without_invoices(self):
        self.assert_rejected(self.make_credit_note(), "invoices")

    def test_rejects_association_without_items(self):
        credit_note = self.make_credit_note()
        invoice = create_invoice(self.point_of_sale, total=Decimal("100.00"))
        self.add_invoice(credit_note, invoice)

        self.assert_rejected(credit_note, "items")

    def test_rejects_when_an_invoice_is_no_longer_issued(self):
        credit_note = self.make_credit_note()
        invoice = create_invoice(self.point_of_sale, total=Decimal("121.00"))
        self.add_invoice(credit_note, invoice, "100.00")
        Invoice.objects.filter(pk=invoice.pk).update(status=InvoiceStatus.CANCELLED)

        self.assert_rejected(credit_note, "invoices")

    def test_rejects_taxed_item_on_credit_note_c(self):
        credit_note = self.make_credit_note(CreditNoteType.CREDIT_NOTE_C)
        invoice = create_invoice(
            self.point_of_sale,
            invoice_type=InvoiceType.INVOICE_C,
            total=Decimal("121.00"),
        )
        self.add_invoice(credit_note, invoice, "100.00")

        self.assert_rejected(credit_note, "items")

    def test_rejects_inactive_point_of_sale(self):
        credit_note = self.make_credit_note()
        invoice = create_invoice(self.point_of_sale, total=Decimal("121.00"))
        self.add_invoice(credit_note, invoice, "100.00")
        self.point_of_sale.is_active = False
        self.point_of_sale.save(update_fields=["is_active"])

        self.assert_rejected(credit_note, "point_of_sale")

    def test_rejects_incomplete_issuer_data(self):
        credit_note = self.make_credit_note()
        invoice = create_invoice(self.point_of_sale, total=Decimal("121.00"))
        self.add_invoice(credit_note, invoice, "100.00")
        Company.objects.filter(pk=self.company.pk).update(legal_name="")

        self.assert_rejected(credit_note, "company")

    def test_non_member_cannot_issue(self):
        credit_note = self.make_credit_note()
        outsider = User.objects.create(id=uuid.uuid4(), email="nc-out@example.com")
        self.client.force_authenticate(user=outsider)

        response = self.issue(credit_note)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
