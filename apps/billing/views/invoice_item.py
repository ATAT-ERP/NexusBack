from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers

from apps.billing.enums.invoice import InvoiceStatus
from apps.billing.models import Invoice, InvoiceItem
from apps.billing.serializers import InvoiceItemSerializer
from apps.billing.views.point_of_sale import CompanyScopedBillingView


class CompanyScopedInvoiceItemView(CompanyScopedBillingView):
    """
    Limita los ítems a una factura de la Company autorizada. Los ítems de
    una factura emitida son inmutables: no admiten alta, edición ni baja.
    @version 1.1
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

    def get_editable_invoice(self):
        """
        Bloquea la fila de la factura y la devuelve sólo si sigue en
        borrador. Debe llamarse dentro de transaction.atomic(). El bloqueo
        es el mismo que toma services/issuing.py, así una edición de ítems
        y una emisión de la misma factura no pueden ejecutarse a la vez.
        @version 1.0
        @author Thiago
        """
        invoice = Invoice.objects.select_for_update().get(pk=self.get_invoice().pk)
        if invoice.status != InvoiceStatus.DRAFT:
            raise serializers.ValidationError(
                {"status": "Los ítems de un comprobante emitido no pueden modificarse."}
            )
        return invoice

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
    Lista los ítems de una factura y agrega uno nuevo mientras esté en
    borrador.
    @version 1.1
    @author Uziel
    """

    def perform_create(self, serializer):
        """
        Asocia el ítem a la factura de la URL si todavía es editable.
        @version 1.1
        @author Uziel
        """
        with transaction.atomic():
            serializer.save(invoice=self.get_editable_invoice())


class InvoiceItemDetailView(
    CompanyScopedInvoiceItemView, generics.RetrieveUpdateDestroyAPIView
):
    """
    Consulta un ítem y, mientras la factura esté en borrador, lo edita o
    lo elimina.
    @version 1.1
    @author Uziel
    """

    def perform_update(self, serializer):
        with transaction.atomic():
            self.get_editable_invoice()
            serializer.save()

    def perform_destroy(self, instance):
        with transaction.atomic():
            self.get_editable_invoice()
            instance.delete()