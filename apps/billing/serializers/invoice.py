from rest_framework import serializers

from apps.billing.models import Invoice
from apps.billing.serializers.invoice_item import InvoiceItemSerializer


class InvoiceSerializer(serializers.ModelSerializer):
    """
    Valida y expone un comprobante. Los totales, el número, el estado y el
    snapshot del emisor son de solo lectura: los calcula el backend.
    @version 1.1
    @author Uziel
    """

    point_of_sale_number = serializers.CharField(
        source="point_of_sale.formatted_number", read_only=True
    )
    formatted_number = serializers.CharField(read_only=True)
    invoice_type_display = serializers.CharField(
        source="get_invoice_type_display", read_only=True
    )
    concept_display = serializers.CharField(
        source="get_concept_display", read_only=True
    )
    items = InvoiceItemSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = (
            "id",
            "point_of_sale",
            "point_of_sale_number",
            "invoice_type",
            "invoice_type_display",
            "status",
            "number",
            "formatted_number",
            "issue_date",
            "concept",
            "concept_display",
            "service_date_from",
            "service_date_to",
            "due_date",
            "receiver_name",
            "receiver_vat_condition",
            "receiver_document_type",
            "receiver_document_number",
            "receiver_address",
            "items",
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