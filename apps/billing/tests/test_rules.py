from datetime import date
from unittest import TestCase

from django.core.exceptions import ValidationError

from apps.billing.enums.invoice import InvoiceConcept, InvoiceType
from apps.billing.enums.tax import TaxTreatment, VATCondition
from apps.billing.services.rules import (
    validate_concept_dates,
    validate_invoice_type,
    validate_vat_discrimination,
)


class InvoiceTypeRulesTests(TestCase):
    def test_invoice_a_valid_and_invalid(self):
        validate_invoice_type(
            InvoiceType.INVOICE_A,
            VATCondition.REGISTERED_RESPONSIBLE,
            VATCondition.REGISTERED_RESPONSIBLE,
        )

        with self.assertRaises(ValidationError):
            validate_invoice_type(
                InvoiceType.INVOICE_A,
                VATCondition.REGISTERED_RESPONSIBLE,
                VATCondition.FINAL_CONSUMER,
            )

    def test_invoice_b_valid_and_invalid(self):
        validate_invoice_type(
            InvoiceType.INVOICE_B,
            VATCondition.REGISTERED_RESPONSIBLE,
            VATCondition.FINAL_CONSUMER,
        )

        with self.assertRaises(ValidationError):
            validate_invoice_type(
                InvoiceType.INVOICE_B,
                VATCondition.REGISTERED_RESPONSIBLE,
                VATCondition.REGISTERED_RESPONSIBLE,
            )

    def test_invoice_c_valid_and_invalid(self):
        validate_invoice_type(
            InvoiceType.INVOICE_C,
            VATCondition.MONOTAX,
            VATCondition.FINAL_CONSUMER,
        )

        with self.assertRaises(ValidationError):
            validate_invoice_type(
                InvoiceType.INVOICE_C,
                VATCondition.REGISTERED_RESPONSIBLE,
                VATCondition.FINAL_CONSUMER,
            )


class ConceptDatesRulesTests(TestCase):
    def test_products_do_not_require_service_dates(self):
        validate_concept_dates(InvoiceConcept.PRODUCTS, None, None)

    def test_services_with_valid_and_invalid_dates(self):
        validate_concept_dates(
            InvoiceConcept.SERVICES, date(2026, 1, 1), date(2026, 1, 31)
        )

        with self.assertRaises(ValidationError):
            validate_concept_dates(
                InvoiceConcept.SERVICES, date(2026, 2, 1), date(2026, 1, 1)
            )

    def test_products_and_services_require_service_dates(self):
        with self.assertRaises(ValidationError):
            validate_concept_dates(InvoiceConcept.PRODUCTS_AND_SERVICES, None, None)


class VATDiscriminationRulesTests(TestCase):
    def test_invoice_c_cannot_discriminate_vat(self):
        with self.assertRaises(ValidationError):
            validate_vat_discrimination(InvoiceType.INVOICE_C, TaxTreatment.TAXED)

    def test_invoice_c_accepts_items_without_discriminated_vat(self):
        for treatment in (
            TaxTreatment.EXEMPT,
            TaxTreatment.UNTAXED,
            TaxTreatment.NOT_DISCRIMINATED,
        ):
            with self.subTest(treatment=treatment):
                validate_vat_discrimination(InvoiceType.INVOICE_C, treatment)

    def test_other_invoice_types_admit_discriminated_vat(self):
        for invoice_type in (InvoiceType.INVOICE_A, InvoiceType.INVOICE_B):
            with self.subTest(invoice_type=invoice_type):
                validate_vat_discrimination(invoice_type, TaxTreatment.TAXED)
