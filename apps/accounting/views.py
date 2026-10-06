from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError as APIValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounting.models import Account
from apps.accounting.models import JournalEntry
from apps.accounting.services import (
    publish_journal_entry,
    reverse_journal_entry,
)
from apps.accounting.serializers.account import (
    AccountListQuerySerializer,
    AccountSerializer,
)
from apps.company.models import Company, CompanyMember
from apps.users.authentication import SupabaseBearerAuthentication


class AccountAccessMixin:
    """
    Limita el plan de cuentas a la Company de la URL y sus miembros.

    @version 1.0
    @author Agustin
    """

    authentication_classes = (SupabaseBearerAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = AccountSerializer

    def get_company(self):
        """
        Obtiene la Company solicitada y exige membership del usuario.

        @version 1.0
        @author Agustin
        """
        company = get_object_or_404(Company, pk=self.kwargs["company_id"])
        if not CompanyMember.objects.filter(
            user=self.request.user,
            company=company,
        ).exists():
            raise PermissionDenied()
        return company

    def get_queryset(self):
        """
        Devuelve únicamente las cuentas de la Company autorizada.

        @version 1.0
        @author Agustin
        """
        return Account.objects.filter(company=self.get_company())


class AccountListCreateView(AccountAccessMixin, generics.ListCreateAPIView):
    """
    Lista y crea cuentas dentro del plan de una Company.

    @version 1.0
    @author Agustin
    """

    def create(self, request, *args, **kwargs):
        """
        Verifica el acceso a la Company antes de validar el payload.

        @version 1.0
        @author Agustin
        """
        self.get_company()
        return super().create(request, *args, **kwargs)

    def get_queryset(self):
        """
        Aplica los filtros válidos al plan de cuentas autorizado.

        @version 1.0
        @author Agustin
        """
        accounts = super().get_queryset()
        filters = AccountListQuerySerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        if "account_type" in filters.validated_data:
            accounts = accounts.filter(account_type=filters.validated_data["account_type"])
        if "is_active" in filters.validated_data:
            accounts = accounts.filter(is_active=filters.validated_data["is_active"])
        return accounts.order_by("code")

    def perform_create(self, serializer):
        """
        Crea la cuenta en la Company autorizada de la URL.

        @version 1.0
        @author Agustin
        """
        serializer.save(company=self.get_company())


class AccountDetailView(AccountAccessMixin, generics.RetrieveUpdateAPIView):
    """
    Obtiene, actualiza o desactiva una cuenta sin eliminarla.

    @version 1.0
    @author Agustin
    """


class JournalEntryPublishView(generics.GenericAPIView):
    """
    Publica un asiento borrador de una Company autorizada.

    @version 1.0
    @author Agustin
    """

    authentication_classes = (SupabaseBearerAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request, company_id, pk):
        """
        Ejecuta la publicación con las validaciones del dominio Accounting.

        @version 1.0
        @author Agustin
        """
        company = get_object_or_404(Company, pk=company_id)
        if not CompanyMember.objects.filter(user=request.user, company=company).exists():
            raise PermissionDenied()
        entry = get_object_or_404(JournalEntry, pk=pk, company=company)
        try:
            entry = publish_journal_entry(entry.pk)
        except ValidationError as error:
            raise APIValidationError(error.messages) from error
        return Response(
            {"id": entry.pk, "number": entry.number, "status": entry.status},
            status=status.HTTP_200_OK,
        )


class JournalEntryReverseView(generics.GenericAPIView):
    """
    Revierte un asiento publicado de una Company autorizada.

    @version 1.0
    @author Agustin
    """

    authentication_classes = (SupabaseBearerAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request, company_id, pk):
        """
        Ejecuta la reversión con las validaciones del dominio Accounting.

        @version 1.0
        @author Agustin
        """
        company = get_object_or_404(Company, pk=company_id)
        if not CompanyMember.objects.filter(user=request.user, company=company).exists():
            raise PermissionDenied()
        entry = get_object_or_404(JournalEntry, pk=pk, company=company)
        try:
            reversal = reverse_journal_entry(entry.pk, user=request.user)
        except ValidationError as error:
            raise APIValidationError(error.messages) from error
        return Response(
            {"id": reversal.pk, "number": reversal.number, "status": reversal.status},
            status=status.HTTP_200_OK,
        )
