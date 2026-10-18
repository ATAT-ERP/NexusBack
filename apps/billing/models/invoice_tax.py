from django.db import models

from apps.billing.enums.tax import TaxType, VATRate


class InvoiceTax(models.Model):
    """
    Detalle de un tributo de un comprobante. Hoy sólo se usa para el IVA
    discriminado por alícuota: cada fila representa la base imponible y el
    importe de una alícuota. Es de sólo lectura y lo genera el backend al
    emitir la factura.
    @version 1.0
    @author Antonio
    """

    invoice = models.ForeignKey(
        "billing.Invoice",
        on_delete=models.CASCADE,
        related_name="taxes",
    )
    tax_type = models.CharField(max_length=20, choices=TaxType.choices)
    vat_rate = models.PositiveSmallIntegerField(
        choices=VATRate.choices,
        blank=True,
        null=True,
    )
    base_amount = models.DecimalField(max_digits=14, decimal_places=2)
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = "billing_invoice_taxes"
        constraints = [
            models.UniqueConstraint(
                fields=["invoice", "tax_type", "vat_rate"],
                name="invoice_tax_unique_by_type_and_rate",
            )
        ]

    def __str__(self):
        return f"InvoiceTax({self.invoice_id}, {self.tax_type}, {self.vat_rate})"
