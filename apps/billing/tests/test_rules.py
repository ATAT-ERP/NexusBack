from datetime import date
from unittest import TestCase

from django.core.exceptions import ValidationError

from apps.billing.enums.invoice import InvoiceConcept, InvoiceType
from apps.billing.enums.tax import VATCondition
from apps.billing.services.rules import validate_concept_dates, validate_invoice_type


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
