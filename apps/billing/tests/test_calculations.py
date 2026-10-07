from decimal import Decimal
from unittest import TestCase

from apps.billing.enums.tax import TaxTreatment, VATRate
from apps.billing.services.calculations import (
    calculate_invoice_totals,
    calculate_item_amounts,
    round_amount,
)


class ItemAmountsTests(TestCase):
    def test_vat_is_calculated_for_each_supported_rate(self):
        for vat_rate, expected_vat in (
            (VATRate.ZERO, "0.00"),
            (VATRate.TWO_AND_HALF, "25.00"),
            (VATRate.FIVE, "50.00"),
            (VATRate.TEN_AND_HALF, "105.00"),
            (VATRate.TWENTY_ONE, "210.00"),
            (VATRate.TWENTY_SEVEN, "270.00"),
        ):
            with self.subTest(vat_rate=vat_rate.label):
                amounts = calculate_item_amounts(
                    Decimal("1"),
                    Decimal("1000.00"),
                    Decimal("0"),
                    TaxTreatment.TAXED,
                    vat_rate,
                )

                self.assertEqual(amounts["net"], Decimal("1000.00"))
                self.assertEqual(amounts["vat"], Decimal(expected_vat))

    def test_discount_is_applied_to_subtotal(self):
        amounts = calculate_item_amounts(
            Decimal("2"),
            Decimal("100.00"),
            Decimal("10"),
            TaxTreatment.TAXED,
            VATRate.TWENTY_ONE,
        )

        self.assertEqual(amounts["subtotal"], Decimal("200.00"))
        self.assertEqual(amounts["discount_amount"], Decimal("20.00"))
        self.assertEqual(amounts["net"], Decimal("180.00"))
        self.assertEqual(amounts["vat"], Decimal("37.80"))
        self.assertEqual(amounts["total"], Decimal("217.80"))

    def test_exempt_item_has_no_vat(self):
        amounts = calculate_item_amounts(
            Decimal("1"), Decimal("100.00"), Decimal("0"), TaxTreatment.EXEMPT
        )

        self.assertEqual(amounts["vat"], Decimal("0.00"))
        self.assertEqual(amounts["total"], Decimal("100.00"))

    def test_untaxed_item_has_no_vat(self):
        amounts = calculate_item_amounts(
            Decimal("1"), Decimal("100.00"), Decimal("0"), TaxTreatment.UNTAXED
        )

        self.assertEqual(amounts["vat"], Decimal("0.00"))
        self.assertEqual(amounts["total"], Decimal("100.00"))

    def test_amounts_are_rounded_half_up_to_two_decimals(self):
        self.assertEqual(round_amount(Decimal("2.665")), Decimal("2.67"))

        amounts = calculate_item_amounts(
            Decimal("1"), Decimal("2.665"), Decimal("0"), TaxTreatment.EXEMPT
        )

        self.assertEqual(amounts["subtotal"], Decimal("2.67"))


class InvoiceTotalsTests(TestCase):
    def test_totals_with_items_of_different_vat_rates(self):
        items = [
            {
                "quantity": Decimal("2"),
                "unit_price": Decimal("100"),
                "discount": Decimal("10"),
                "tax_treatment": TaxTreatment.TAXED,
                "vat_rate": VATRate.TWENTY_ONE,
            },
            {
                "quantity": Decimal("1"),
                "unit_price": Decimal("1000"),
                "discount": Decimal("0"),
                "tax_treatment": TaxTreatment.TAXED,
                "vat_rate": VATRate.TEN_AND_HALF,
            },
            {
                "quantity": Decimal("3"),
                "unit_price": Decimal("33.335"),
                "discount": Decimal("0"),
                "tax_treatment": TaxTreatment.TAXED,
                "vat_rate": VATRate.TWENTY_SEVEN,
            },
            {
                "quantity": Decimal("1"),
                "unit_price": Decimal("50"),
                "discount": Decimal("0"),
                "tax_treatment": TaxTreatment.UNTAXED,
            },
            {
                "quantity": Decimal("1"),
                "unit_price": Decimal("25.50"),
                "discount": Decimal("0"),
                "tax_treatment": TaxTreatment.NOT_DISCRIMINATED,
            },
            {
                "quantity": Decimal("4"),
                "unit_price": Decimal("10"),
                "discount": Decimal("25"),
                "tax_treatment": TaxTreatment.EXEMPT,
            },
        ]

        totals = calculate_invoice_totals(items)

        self.assertEqual(
            totals,
            {
                "net_taxed": Decimal("1280.01"),
                "net_untaxed": Decimal("75.50"),
                "net_exempt": Decimal("30.00"),
                "vat_amount": Decimal("169.80"),
                "total": Decimal("1555.31"),
            },
        )
