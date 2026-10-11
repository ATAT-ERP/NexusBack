from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.response import Response

from apps.billing.enums.invoice import InvoiceStatus
from apps.billing.models import Invoice
from apps.billing.serializers import InvoiceFilterSerializer, InvoiceSerializer
from apps.billing.services.issuing import issue_invoice
from apps.billing.views.point_of_sale import CompanyScopedBillingView


class CompanyScopedInvoiceView(CompanyScopedBillingView):
    """
    Limita las facturas a los puntos de venta de la Company autorizada y
    rechaza puntos de venta de otra Company al crear o editar. Una factura
    emitida es inmutable: no admite edición.
    @version 1.1
    @author Uziel
    """

    serializer_class = InvoiceSerializer

    def get_queryset(self):
        """
        Retorna las facturas de la Company indicada en la URL.
        @version 1.1
        @author Uziel
        """
        return Invoice.objects.filter(
            point_of_sale__fiscal_profile=self.get_fiscal_profile()
        ).select_related("point_of_sale").prefetch_related("items")

    def save_in_company(self, serializer):
        """
        Guarda la factura sólo si su punto de venta pertenece a la Company
        autorizada.
        @version 1.0
        @author Uziel
        """
        point_of_sale = serializer.validated_data.get("point_of_sale")
        if (
            point_of_sale is not None
            and point_of_sale.fiscal_profile_id != self.get_fiscal_profile().pk
        ):
            raise serializers.ValidationError(
                {"point_of_sale": "El punto de venta no pertenece a la compañía."}
            )
        serializer.save()

    def perform_create(self, serializer):
        self.save_in_company(serializer)

    def perform_update(self, serializer):
        if serializer.instance.status == InvoiceStatus.ISSUED:
            raise serializers.ValidationError(
                {"status": "Un comprobante emitido no puede modificarse."}
            )
        self.save_in_company(serializer)


class InvoiceListCreateView(CompanyScopedInvoiceView, generics.ListCreateAPIView):
    """
    Lista las facturas de la Company autorizada, con filtros opcionales, y
    crea una nueva.
    @version 1.1
    @author Uziel
    """

    def get_queryset(self):
        """
        Aplica los filtros de la query string: status, invoice_type,
        point_of_sale, issue_date_from, issue_date_to, receiver y number.
        @version 1.0
        @author Thiago
        """
        queryset = super().get_queryset().order_by("-created_at", "-id")

        filters = InvoiceFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        params = filters.validated_data

        if "status" in params:
            queryset = queryset.filter(status=params["status"])
        if "invoice_type" in params:
            queryset = queryset.filter(invoice_type=params["invoice_type"])
        if "point_of_sale" in params:
            queryset = queryset.filter(point_of_sale_id=params["point_of_sale"])
        if "issue_date_from" in params:
            queryset = queryset.filter(issue_date__gte=params["issue_date_from"])
        if "issue_date_to" in params:
            queryset = queryset.filter(issue_date__lte=params["issue_date_to"])
        if "receiver" in params:
            term = params["receiver"]
            queryset = queryset.filter(
                Q(receiver_name__icontains=term)
                | Q(receiver_document_number__icontains=term)
            )
        if "number" in params:
            queryset = self.filter_by_number(queryset, params["number"])
        return queryset

    @staticmethod
    def filter_by_number(queryset, value):
        """
        Filtra por correlativo (15) o por comprobante completo
        (00001-00000015).
        @version 1.0
        @author Thiago
        """
        if "-" in value:
            point_of_sale_number, number = value.split("-")
            return queryset.filter(
                point_of_sale__number=int(point_of_sale_number),
                number=int(number),
            )
        return queryset.filter(number=int(value))


class InvoiceDetailView(CompanyScopedInvoiceView, generics.RetrieveUpdateAPIView):
    """
    Consulta y edita una factura en borrador de la Company autorizada.
    @version 1.0
    @author Uziel
    """


class InvoiceIssueView(CompanyScopedInvoiceView, generics.GenericAPIView):
    """
    Emite una factura de la Company autorizada delegando todo el flujo en
    services/issuing.py.
    @version 1.0
    @author Thiago
    """

    def post(self, request, *args, **kwargs):
        invoice = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
        try:
            invoice = issue_invoice(invoice)
        except DjangoValidationError as error:
            if hasattr(error, "error_dict"):
                raise serializers.ValidationError(error.message_dict)
            raise serializers.ValidationError({"non_field_errors": error.messages})
        return Response(self.get_serializer(invoice).data)