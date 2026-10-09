from rest_framework import generics, serializers

from apps.billing.models import Invoice
from apps.billing.serializers import InvoiceSerializer
from apps.billing.views.point_of_sale import CompanyScopedBillingView


class CompanyScopedInvoiceView(CompanyScopedBillingView):
    """
    Limita las facturas a los puntos de venta de la Company autorizada y
    rechaza puntos de venta de otra Company al crear o editar.
    @version 1.0
    @author Uziel
    """

    serializer_class = InvoiceSerializer

    def get_queryset(self):
        """
        Retorna las facturas de la Company indicada en la URL.
        @version 1.0
        @author Uziel
        """
        return Invoice.objects.filter(
            point_of_sale__fiscal_profile=self.get_fiscal_profile()
        )

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
        self.save_in_company(serializer)


class InvoiceListCreateView(CompanyScopedInvoiceView, generics.ListCreateAPIView):
    """
    Lista las facturas de la Company autorizada y crea una nueva.
    @version 1.0
    @author Uziel
    """


class InvoiceDetailView(CompanyScopedInvoiceView, generics.RetrieveUpdateAPIView):
    """
    Consulta y edita una factura de la Company autorizada.
    @version 1.0
    @author Uziel
    """
