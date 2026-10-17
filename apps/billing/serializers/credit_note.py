from rest_framework import serializers

from apps.billing.models import CreditNote, PointOfSale
from apps.billing.serializers.credit_note_invoice import CreditNoteInvoiceSerializer


class CreditNoteSerializer(serializers.ModelSerializer):
    """
    Valida y expone una Nota de Crédito. Sólo el punto de venta y el tipo son
    escribibles: las facturas se asocian por su propio endpoint y el resto lo
    completa el backend.
    @version 1.0
    @author Uziel
    """

    credit_note_invoices = CreditNoteInvoiceSerializer(many=True, read_only=True)

    class Meta:
        model = CreditNote
        fields = (
            "id",
            "point_of_sale",
            "credit_note_type",
            "status",
            "number",
            "issue_date",
            "credit_note_invoices",
            "receiver_name",
            "receiver_vat_condition",
            "receiver_document_type",
            "receiver_document_number",
            "receiver_address",
            "net_taxed",
            "net_untaxed",
            "net_exempt",
            "vat_amount",
            "total",
            "issuer_legal_name",
            "issuer_tax_id",
            "issuer_address",
            "issuer_vat_condition",
            "issuer_gross_income",
            "issuer_activity_start_date",
            "created_at",
            "updated_at",
        )
        read_only_fields = tuple(
            field
            for field in fields
            if field not in ("point_of_sale", "credit_note_type")
        )

    def get_fields(self):
        """
        Limita point_of_sale a los puntos de venta del fiscal profile del
        contexto, para que uno inexistente y uno ajeno respondan igual.
        @version 1.0
        @author Uziel
        """
        fields = super().get_fields()
        fields["point_of_sale"].queryset = PointOfSale.objects.filter(
            fiscal_profile=self.context["fiscal_profile"]
        )
        return fields
