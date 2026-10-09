from django.shortcuts import get_object_or_404
from rest_framework import generics

from apps.billing.models import Invoice, InvoiceItem
from apps.billing.serializers import InvoiceItemSerializer
from apps.billing.views.point_of_sale import CompanyScopedBillingView


class CompanyScopedInvoiceItemView(CompanyScopedBillingView):
    """
    Limita los ítems a una factura de la Company autorizada.
    @version 1.0
    @author Uziel
    """

    serializer_class = InvoiceItemSerializer

    def get_invoice(self):
        """
        Obtiene la factura de la URL sólo si pertenece a la Company autorizada.
        @version 1.0
        @author Uziel
        """
        return get_object_or_404(
            Invoice,
            pk=self.kwargs["invoice_id"],
            point_of_sale__fiscal_profile=self.get_fiscal_profile(),
        )

    def get_queryset(self):
        """
        Retorna los ítems de la factura indicada en la URL.
        @version 1.0
        @author Uziel
        """
        return InvoiceItem.objects.filter(invoice=self.get_invoice())


class InvoiceItemListCreateView(
    CompanyScopedInvoiceItemView, generics.ListCreateAPIView
):
    """
    Lista los ítems de una factura y agrega uno nuevo.
    @version 1.0
    @author Uziel
    """

    def perform_create(self, serializer):
        """
        Asocia el ítem a la factura de la URL.
        @version 1.0
        @author Uziel
        """
        serializer.save(invoice=self.get_invoice())


class InvoiceItemDetailView(
    CompanyScopedInvoiceItemView, generics.RetrieveUpdateDestroyAPIView
):
    """
    Consulta, edita y elimina un ítem de una factura de la Company autorizada.
    @version 1.0
    @author Uziel
    """
