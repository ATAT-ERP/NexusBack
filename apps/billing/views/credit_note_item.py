from django.db import transaction
from rest_framework import generics

from apps.billing.models import CreditNoteItem
from apps.billing.serializers import CreditNoteItemSerializer
from apps.billing.views.credit_note import CompanyScopedCreditNoteChildView


class CompanyScopedCreditNoteItemView(CompanyScopedCreditNoteChildView):
    """
    Limita los ítems a una Nota de Crédito de la Company autorizada. Los
    ítems de una Nota de Crédito emitida son inmutables: no admiten alta,
    edición ni baja.
    @version 1.0
    @author Uziel
    """

    serializer_class = CreditNoteItemSerializer

    def get_queryset(self):
        """
        Retorna los ítems de la Nota de Crédito indicada en la URL.
        @version 1.0
        @author Uziel
        """
        return CreditNoteItem.objects.filter(
            credit_note_invoice__credit_note=self.get_credit_note()
        ).order_by("id")


class CreditNoteItemListCreateView(
    CompanyScopedCreditNoteItemView, generics.ListCreateAPIView
):
    """
    Lista los ítems de una Nota de Crédito y agrega uno nuevo mientras esté
    en borrador.
    @version 1.0
    @author Uziel
    """

    def perform_create(self, serializer):
        with transaction.atomic():
            self.get_editable_credit_note()
            serializer.save()


class CreditNoteItemDetailView(
    CompanyScopedCreditNoteItemView, generics.RetrieveUpdateDestroyAPIView
):
    """
    Consulta un ítem y, mientras la Nota de Crédito esté en borrador, lo
    edita o lo elimina.
    @version 1.0
    @author Uziel
    """

    def perform_update(self, serializer):
        with transaction.atomic():
            self.get_editable_credit_note()
            serializer.save()

    def perform_destroy(self, instance):
        with transaction.atomic():
            self.get_editable_credit_note()
            instance.delete()
