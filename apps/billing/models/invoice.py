from django.db import models

from apps.billing.enums.invoice import (
    DocumentType,
    InvoiceConcept,
    InvoiceStatus,
    InvoiceType,
)
from apps.billing.enums.tax import VATCondition


class Invoice(models.Model):
    """
    Comprobante emitido desde un punto de venta. El número, la fecha de
    emisión y el snapshot del emisor permanecen vacíos hasta la emisión.
    @version 1.0
    @author Uziel
    """

    point_of_sale = models.ForeignKey(
        "billing.PointOfSale",
        on_delete=models.CASCADE,
        related_name="invoices",
    )
    invoice_type = models.PositiveSmallIntegerField(choices=InvoiceType.choices)
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.DRAFT,
    )
    number = models.PositiveIntegerField(blank=True, null=True)
    issue_date = models.DateField(blank=True, null=True)
    concept = models.PositiveSmallIntegerField(choices=InvoiceConcept.choices)
    service_date_from = models.DateField(blank=True, null=True)
    service_date_to = models.DateField(blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)

    receiver_name = models.CharField(max_length=255)
    receiver_vat_condition = models.PositiveSmallIntegerField(
        choices=VATCondition.choices
    )
    receiver_document_type = models.PositiveSmallIntegerField(
        choices=DocumentType.choices
    )
    receiver_document_number = models.CharField(max_length=20)
    receiver_address = models.CharField(max_length=255)

    net_taxed = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_untaxed = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_exempt = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    vat_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    issuer_legal_name = models.CharField(max_length=255, blank=True, null=True)
    issuer_tax_id = models.CharField(max_length=20, blank=True, null=True)
    issuer_address = models.CharField(max_length=255, blank=True, null=True)
    issuer_vat_condition = models.PositiveSmallIntegerField(
        choices=VATCondition.choices,
        blank=True,
        null=True,
    )
    issuer_gross_income = models.CharField(max_length=30, blank=True, null=True)
    issuer_activity_start_date = models.DateField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "billing_invoices"

    def __str__(self):
        return f"Invoice({self.point_of_sale_id}, {self.invoice_type}, {self.number})"

    @property
    def formatted_number(self):
        """
        Representa el comprobante como punto de venta y número, por
        ejemplo 00001-00000015. Es None mientras sea un borrador.
        @version 1.0
        @author Thiago
        """
        if self.number is None:
            return None
        return f"{self.point_of_sale.formatted_number}-{self.number:08d}"
