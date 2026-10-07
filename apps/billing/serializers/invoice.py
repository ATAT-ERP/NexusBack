from rest_framework import serializers

from apps.billing.models import Invoice


class InvoiceSerializer(serializers.ModelSerializer):
    """
    Valida y expone un comprobante. Los totales, el número, el estado y el
    snapshot del emisor son de solo lectura: los calcula el backend.
    @version 1.0
    @author Uziel
    """

    class Meta:
        model = Invoice
        fields = (
            "id",
            "point_of_sale",
            "invoice_type",
            "status",
            "number",
            "issue_date",
            "concept",
            "service_date_from",
            "service_date_to",
            "due_date",
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
        read_only_fields = (
            "id",
            "status",
            "number",
            "issue_date",
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
