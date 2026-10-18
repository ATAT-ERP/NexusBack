from django.db import transaction
from rest_framework import generics, status
from rest_framework.response import Response

from apps.billing.models import CreditNoteInvoice
from apps.billing.serializers import (
    CreditNoteInvoiceCreateSerializer,
    CreditNoteInvoiceSerializer,
)
from apps.billing.views.credit_note import CompanyScopedCreditNoteChildView


class CompanyScopedCreditNoteInvoiceView(CompanyScopedCreditNoteChildView):
    """
    Limita las asociaciones a las de una Nota de Crédito de la Company
    autorizada.
    @version 1.0
    @author Uziel
    """

    serializer_class = CreditNoteInvoiceSerializer

    def get_queryset(self):
        """
        Retorna las asociaciones de la Nota de Crédito indicada en la URL.
        @version 1.0
        @author Uziel
        """
        return CreditNoteInvoice.objects.filter(credit_note=self.get_credit_note())


class CreditNoteInvoiceListCreateView(
    CompanyScopedCreditNoteInvoiceView, generics.ListAPIView
):
    """
    Lista las facturas asociadas a una Nota de Crédito y asocia nuevas de
    forma acumulativa mientras esté en borrador.
    @version 1.0
    @author Uziel
    """

    def post(self, request, *args, **kwargs):
        """
        Asocia todas las facturas del body o ninguna. Valida con la fila de
        la Nota de Crédito bloqueada para que dos asociaciones simultáneas
        no puedan mezclar receptores.
        @version 1.0
        @author Uziel
        """
        with transaction.atomic():
            credit_note = self.get_editable_credit_note()
            serializer = CreditNoteInvoiceCreateSerializer(
                data=request.data,
                context={**self.get_serializer_context(), "credit_note": credit_note},
            )
            serializer.is_valid(raise_exception=True)
            associations = CreditNoteInvoice.objects.bulk_create(
                CreditNoteInvoice(credit_note=credit_note, invoice=invoice)
                for invoice in serializer.validated_data["invoices"]
            )
        return Response(
            self.get_serializer(associations, many=True).data,
            status=status.HTTP_201_CREATED,
        )


class CreditNoteInvoiceDetailView(
    CompanyScopedCreditNoteInvoiceView, generics.DestroyAPIView
):
    """
    Desasocia una factura de una Nota de Crédito en borrador. Los ítems de
    la asociación se eliminan en cascada.
    @version 1.0
    @author Uziel
    """

    def perform_destroy(self, instance):
        with transaction.atomic():
            self.get_editable_credit_note()
            instance.delete()
