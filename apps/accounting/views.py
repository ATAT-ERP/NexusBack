from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from apps.accounting.models import Account
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
