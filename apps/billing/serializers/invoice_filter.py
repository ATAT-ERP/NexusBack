from rest_framework import serializers

from apps.billing.enums.invoice import InvoiceStatus, InvoiceType


class InvoiceFilterSerializer(serializers.Serializer):
    """
    Valida los parámetros de búsqueda del listado de comprobantes para que
    un valor inválido responda 400 en vez de romper la consulta. `number`
    acepta el correlativo (15) o el comprobante completo (00001-00000015).
    @version 1.0
    @author Thiago
    """

    status = serializers.ChoiceField(choices=InvoiceStatus.choices, required=False)
    invoice_type = serializers.ChoiceField(choices=InvoiceType.choices, required=False)
    point_of_sale = serializers.IntegerField(required=False)
    issue_date_from = serializers.DateField(required=False)
    issue_date_to = serializers.DateField(required=False)
    receiver = serializers.CharField(required=False)
    number = serializers.RegexField(r"^(\d{1,5}-)?\d{1,8}$", required=False)