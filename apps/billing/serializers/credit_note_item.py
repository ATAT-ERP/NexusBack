from apps.billing.models import CreditNoteInvoice, CreditNoteItem
from apps.billing.serializers.invoice_item import InvoiceItemSerializer


class CreditNoteItemSerializer(InvoiceItemSerializer):
    """
    Valida y expone un ítem de Nota de Crédito. A diferencia del ítem de
    factura, la asociación que acredita viaja en el body y se limita a las
    de la Nota de Crédito del contexto.
    @version 1.0
    @author Uziel
    """

    class Meta(InvoiceItemSerializer.Meta):
        model = CreditNoteItem
        fields = (
            "id",
            "credit_note_invoice",
            "description",
            "quantity",
            "unit_price",
            "discount",
            "tax_treatment",
            "vat_rate",
        )
        read_only_fields = ("id",)

    def get_fields(self):
        """
        Limita credit_note_invoice a las asociaciones de la Nota de Crédito
        del contexto.
        @version 1.0
        @author Uziel
        """
        fields = super().get_fields()
        fields["credit_note_invoice"].queryset = CreditNoteInvoice.objects.filter(
            credit_note=self.context["credit_note"]
        )
        return fields
