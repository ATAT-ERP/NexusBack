from django.db import models

from apps.billing.enums.tax import TaxTreatment, VATRate


class CreditNoteItem(models.Model):
    """
    Ítem de una Nota de Crédito, asociado a la factura que acredita. La
    alícuota de IVA es opcional porque no todos los tratamientos fiscales la
    llevan.
    @version 1.0
    @author Uziel
    """

    credit_note_invoice = models.ForeignKey(
        "billing.CreditNoteInvoice",
        on_delete=models.CASCADE,
        related_name="items",
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_treatment = models.CharField(max_length=20, choices=TaxTreatment.choices)
    vat_rate = models.PositiveSmallIntegerField(
        choices=VATRate.choices,
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "billing_credit_note_items"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(discount__gte=0, discount__lte=100),
                name="credit_note_item_discount_between_0_and_100",
            )
        ]

    def __str__(self):
        return f"CreditNoteItem({self.credit_note_invoice_id}, {self.description})"
