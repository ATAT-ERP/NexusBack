from django.test import TestCase

from apps.billing.enums import InvoiceType, VATCondition
from apps.billing.models import FiscalProfile, PointOfSale
from apps.billing.services.numbering import next_invoice_number
from apps.company.models import Company


class InvoiceSequenceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Empresa Facturación")
        self.fiscal_profile = FiscalProfile.objects.create(
            company=self.company,
            vat_condition=VATCondition.REGISTERED_RESPONSIBLE,
        )
        self.point_of_sale = PointOfSale.objects.create(
            fiscal_profile=self.fiscal_profile,
            number=1,
        )

    def test_first_invoice_number_is_1(self):
        number = next_invoice_number(self.point_of_sale, InvoiceType.INVOICE_A)

        self.assertEqual(number, 1)

    def test_numbers_increment_correctly(self):
        first = next_invoice_number(self.point_of_sale, InvoiceType.INVOICE_A)
        second = next_invoice_number(self.point_of_sale, InvoiceType.INVOICE_A)
        third = next_invoice_number(self.point_of_sale, InvoiceType.INVOICE_A)

        self.assertEqual([first, second, third], [1, 2, 3])

    def test_sequences_are_independent_per_invoice_type(self):
        next_invoice_number(self.point_of_sale, InvoiceType.INVOICE_A)
        next_invoice_number(self.point_of_sale, InvoiceType.INVOICE_A)
        first_b = next_invoice_number(self.point_of_sale, InvoiceType.INVOICE_B)

        self.assertEqual(first_b, 1)

    def test_sequences_are_independent_per_point_of_sale(self):
        other_point_of_sale = PointOfSale.objects.create(
            fiscal_profile=self.fiscal_profile,
            number=2,
        )

        next_invoice_number(self.point_of_sale, InvoiceType.INVOICE_A)
        first_on_other_pos = next_invoice_number(other_point_of_sale, InvoiceType.INVOICE_A)

        self.assertEqual(first_on_other_pos, 1)

    def test_no_number_reuse_after_multiple_calls(self):
        numbers = [
            next_invoice_number(self.point_of_sale, InvoiceType.INVOICE_C)
            for _ in range(5)
        ]

        self.assertEqual(numbers, [1, 2, 3, 4, 5])
        self.assertEqual(len(set(numbers)), 5)