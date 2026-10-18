from rest_framework import serializers

from apps.billing.enums.invoice import INVOICE_TYPE_BY_CREDIT_NOTE_TYPE, InvoiceStatus
from apps.billing.models import CreditNoteInvoice, Invoice


class CreditNoteInvoiceSerializer(serializers.ModelSerializer):
    """
    Expone la asociación de una factura a una Nota de Crédito. Es de sólo
    lectura: las asociaciones se crean con CreditNoteInvoiceCreateSerializer
    y el total lo fija la emisión.
    @version 1.0
    @author Uziel
    """

    class Meta:
        model = CreditNoteInvoice
        fields = ("id", "credit_note", "invoice", "total")
        read_only_fields = fields


class CreditNoteInvoiceCreateSerializer(serializers.Serializer):
    """
    Valida la lista de facturas a asociar a una Nota de Crédito en borrador.
    Debe ejecutarse con la fila de la Nota de Crédito bloqueada, porque
    compara contra las asociaciones ya existentes.
    @version 1.0
    @author Uziel
    """

    invoices = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Invoice.objects.none(), allow_empty=False
    )

    def get_fields(self):
        """
        Limita invoices a las facturas del fiscal profile del contexto, para
        que una inexistente y una ajena respondan igual.
        @version 1.0
        @author Uziel
        """
        fields = super().get_fields()
        fields["invoices"].child_relation.queryset = Invoice.objects.filter(
            point_of_sale__fiscal_profile=self.context["fiscal_profile"]
        )
        return fields

    def validate_invoices(self, invoices):
        """
        Exige facturas emitidas, del tipo homólogo al de la Nota de Crédito,
        no repetidas ni ya asociadas, y con el mismo receptor entre sí y con
        las ya asociadas.
        @version 1.0
        @author Uziel
        """
        credit_note = self.context["credit_note"]
        expected_type = INVOICE_TYPE_BY_CREDIT_NOTE_TYPE[credit_note.credit_note_type]
        associated = list(credit_note.invoices.all())
        taken_ids = {invoice.pk for invoice in associated}

        for invoice in invoices:
            if invoice.pk in taken_ids:
                raise serializers.ValidationError(
                    f"La factura {invoice.pk} está repetida o ya asociada."
                )
            taken_ids.add(invoice.pk)
            if invoice.status != InvoiceStatus.ISSUED:
                raise serializers.ValidationError(
                    f"La factura {invoice.pk} debe estar emitida."
                )
            if invoice.invoice_type != expected_type:
                raise serializers.ValidationError(
                    f"La factura {invoice.pk} no es del tipo homólogo a la Nota de Crédito."
                )

        receivers = {
            (invoice.receiver_document_type, invoice.receiver_document_number)
            for invoice in (*associated, *invoices)
        }
        if len(receivers) > 1:
            raise serializers.ValidationError(
                "Todas las facturas deben tener el mismo receptor."
            )
        return invoices
