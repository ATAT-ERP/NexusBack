from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.response import Response

from apps.billing.enums.invoice import InvoiceStatus
from apps.billing.models import CreditNote
from apps.billing.serializers import CreditNoteSerializer
from apps.billing.services.issuing import issue_credit_note
from apps.billing.views.point_of_sale import CompanyScopedBillingView


class CompanyScopedCreditNoteView(CompanyScopedBillingView):
    """
    Limita las Notas de Crédito a los puntos de venta de la Company
    autorizada y rechaza puntos de venta de otra Company al crear.
    @version 1.0
    @author Uziel
    """

    serializer_class = CreditNoteSerializer

    def get_queryset(self):
        """
        Retorna las Notas de Crédito de la Company indicada en la URL.
        @version 1.0
        @author Uziel
        """
        return (
            CreditNote.objects.filter(
                point_of_sale__fiscal_profile=self.get_fiscal_profile()
            )
            .select_related("point_of_sale")
            .prefetch_related("credit_note_invoices")
            .order_by("-created_at", "-id")
        )

    def get_serializer_context(self):
        """
        Agrega el fiscal profile de la Company autorizada para acotar el
        punto de venta del serializer.
        @version 1.0
        @author Uziel
        """
        return {
            **super().get_serializer_context(),
            "fiscal_profile": self.get_fiscal_profile(),
        }


class CompanyScopedCreditNoteChildView(CompanyScopedBillingView):
    """
    Base de los recursos que cuelgan de una Nota de Crédito de la Company
    autorizada (facturas asociadas e ítems). Sólo admiten alta, edición y
    baja mientras la Nota de Crédito esté en borrador.
    @version 1.0
    @author Uziel
    """

    def get_credit_note(self):
        """
        Obtiene la Nota de Crédito de la URL sólo si pertenece a la Company
        autorizada.
        @version 1.0
        @author Uziel
        """
        return get_object_or_404(
            CreditNote,
            pk=self.kwargs["credit_note_id"],
            point_of_sale__fiscal_profile=self.get_fiscal_profile(),
        )

    def get_editable_credit_note(self):
        """
        Bloquea la fila de la Nota de Crédito y la devuelve sólo si sigue en
        borrador. Debe llamarse dentro de transaction.atomic(). Es el mismo
        bloqueo que tomará la emisión, así una edición y una emisión de la
        misma Nota de Crédito no pueden ejecutarse a la vez.
        @version 1.0
        @author Uziel
        """
        credit_note = CreditNote.objects.select_for_update().get(
            pk=self.get_credit_note().pk
        )
        if credit_note.status != InvoiceStatus.DRAFT:
            raise serializers.ValidationError(
                {"status": "Una Nota de Crédito emitida no puede modificarse."}
            )
        return credit_note

    def get_serializer_context(self):
        """
        Agrega el fiscal profile de la Company autorizada y la Nota de
        Crédito de la URL para acotar las relaciones del serializer.
        @version 1.0
        @author Uziel
        """
        return {
            **super().get_serializer_context(),
            "fiscal_profile": self.get_fiscal_profile(),
            "credit_note": self.get_credit_note(),
        }


class CreditNoteListCreateView(CompanyScopedCreditNoteView, generics.ListCreateAPIView):
    """
    Lista las Notas de Crédito de la Company autorizada y crea un borrador
    sin facturas asociadas.
    @version 1.0
    @author Uziel
    """


class CreditNoteDetailView(CompanyScopedCreditNoteView, generics.RetrieveAPIView):
    """
    Consulta una Nota de Crédito de la Company autorizada.
    @version 1.0
    @author Uziel
    """


class CreditNoteIssueView(CompanyScopedCreditNoteView, generics.GenericAPIView):
    """
    Emite una Nota de Crédito de la Company autorizada delegando todo el
    flujo en services/issuing.py.
    @version 1.0
    @author Uziel
    """

    def post(self, request, *args, **kwargs):
        credit_note = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
        try:
            credit_note = issue_credit_note(credit_note)
        except DjangoValidationError as error:
            if hasattr(error, "error_dict"):
                raise serializers.ValidationError(error.message_dict)
            raise serializers.ValidationError({"non_field_errors": error.messages})
        return Response(self.get_serializer(credit_note).data)
