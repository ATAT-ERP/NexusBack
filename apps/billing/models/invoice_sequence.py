from django.db import models

from apps.billing.enums import InvoiceType


class InvoiceSequence(models.Model):
    """
    Correlativo interno por punto de venta y tipo de comprobante.
    Es una responsabilidad interna: no se expone CRUD público, su
    número solo se incrementa a través de services/numbering.py.
    @version 1.0
    @author Thiago
    """

    point_of_sale = models.ForeignKey(
        "billing.PointOfSale",
        on_delete=models.CASCADE,
        related_name="invoice_sequences",
    )
    invoice_type = models.PositiveSmallIntegerField(choices=InvoiceType.choices)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "billing_invoice_sequences"
        constraints = [
            models.UniqueConstraint(
                fields=["point_of_sale", "invoice_type"],
                name="unique_sequence_per_point_of_sale_and_invoice_type",
            )
        ]

    def __str__(self):
        return f"InvoiceSequence({self.point_of_sale_id}, {self.invoice_type}, {self.last_number})"