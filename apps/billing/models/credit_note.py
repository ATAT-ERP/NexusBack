from django.db import models

from apps.billing.enums.invoice import CreditNoteType, DocumentType, InvoiceStatus
from apps.billing.enums.tax import VATCondition


class CreditNote(models.Model):
    """
    Nota de Crédito emitida desde un punto de venta que acredita total o
    parcialmente una o más facturas. El número, la fecha de emisión y los
    snapshots del emisor y del receptor permanecen vacíos hasta la emisión.
    @version 1.0
    @author Uziel
    """

    point_of_sale = models.ForeignKey(
        "billing.PointOfSale",
        on_delete=models.CASCADE,
        related_name="credit_notes",
    )
    credit_note_type = models.PositiveSmallIntegerField(choices=CreditNoteType.choices)
    status = models.CharField(
        max_length=20,
        choices=[
            (InvoiceStatus.DRAFT, InvoiceStatus.DRAFT.label),
            (InvoiceStatus.ISSUED, InvoiceStatus.ISSUED.label),
        ],
        default=InvoiceStatus.DRAFT,
    )
    number = models.PositiveIntegerField(blank=True, null=True)
    issue_date = models.DateField(blank=True, null=True)
    invoices = models.ManyToManyField(
        "billing.Invoice",
        through="billing.CreditNoteInvoice",
        related_name="credit_notes",
    )

    receiver_name = models.CharField(max_length=255, blank=True, null=True)
    receiver_vat_condition = models.PositiveSmallIntegerField(
        choices=VATCondition.choices,
        blank=True,
        null=True,
    )
    receiver_document_type = models.PositiveSmallIntegerField(
        choices=DocumentType.choices,
        blank=True,
        null=True,
    )
    receiver_document_number = models.CharField(max_length=20, blank=True, null=True)
    receiver_address = models.CharField(max_length=255, blank=True, null=True)

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
        db_table = "billing_credit_notes"

    def __str__(self):
        return (
            f"CreditNote({self.point_of_sale_id}, {self.credit_note_type}, {self.number})"
        )
