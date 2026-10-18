from django.db import models


class CreditNoteInvoice(models.Model):
    """
    Asociación entre una Nota de Crédito y una factura que acredita. El total
    es el importe acreditado de esa factura, IVA incluido: vale 0 mientras la
    Nota de Crédito es un borrador y se fija al emitirla.
    @version 1.0
    @author Uziel
    """

    credit_note = models.ForeignKey(
        "billing.CreditNote",
        on_delete=models.CASCADE,
        related_name="credit_note_invoices",
    )
    invoice = models.ForeignKey(
        "billing.Invoice",
        on_delete=models.PROTECT,
        related_name="credit_note_invoices",
    )
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = "billing_credit_note_invoices"
        constraints = [
            models.UniqueConstraint(
                fields=["credit_note", "invoice"],
                name="credit_note_invoice_unique_per_credit_note",
            ),
            models.CheckConstraint(
                condition=models.Q(total__gte=0),
                name="credit_note_invoice_total_gte_0",
            ),
        ]

    def __str__(self):
        return f"CreditNoteInvoice({self.credit_note_id}, {self.invoice_id})"
