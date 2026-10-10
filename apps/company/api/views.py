import re

from django.db import transaction
from django.db.models import Q
from rest_framework import generics, serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.company.api.serializers import CompanySerializer
from apps.company.models import Company, CompanyMember, CompanyRole, normalize_tax_id
from apps.users.authentication import SupabaseBearerAuthentication


class CompanyListView(generics.ListCreateAPIView):
    """
    Lista compañías registradas y permite dar de alta una nueva.

    @version 2.0
    @author Agustin, Antonio, Uziel
    """

    serializer_class = CompanySerializer
    authentication_classes = (SupabaseBearerAuthentication,)
    permission_classes = (IsAuthenticated,)

    def perform_create(self, serializer):
        """
        Crea una compañía y asigna al usuario creador como owner.

        @version 1.0
        @author Agustin
        """
        with transaction.atomic():
            company = serializer.save()
            owner_role = CompanyRole.objects.get(code="owner")
            CompanyMember.objects.create(
                user=self.request.user,
                company=company,
                role=owner_role,
            )

    def get_queryset(self):
        """
        Retorna compañías del usuario filtradas por estado. Por defecto solo activas.

        @version 1.1
        @author Uziel
        """
        is_active = self.request.query_params.get("is_active", "true").lower()

        companies = Company.objects.filter(memberships__user=self.request.user)

        if is_active == "all":
            return companies.distinct()

        if is_active == "false":
            return companies.filter(is_active=False).distinct()

        # Caso por defecto: solo activas
        return companies.filter(is_active=True).distinct()

    def handle_exception(self, error):
        if isinstance(error, serializers.ValidationError):
            return Response(
                {
                    "code": "NEX-COM-001",
                    "message": "Los datos enviados no son válidos.",
                    "errors": error.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().handle_exception(error)


class CompanySearchView(generics.ListAPIView):
    """
    Búsqueda de compañías por nombre, razón social o CUIT.

    @version 2.0
    @author Antonio
    """

    serializer_class = CompanySerializer
    authentication_classes = (SupabaseBearerAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        raw_query = self.request.query_params.get("q", "")
        query = re.sub(r"\s+", " ", raw_query).strip()
        if not query:
            return Company.objects.none()

        queryset = Company.objects.filter(
            memberships__user=self.request.user,
        ).filter(
            Q(name__icontains=query) | Q(legal_name__icontains=query)
        )

        normalized = normalize_tax_id(query)
        if normalized and normalized.isdigit():
            queryset = queryset | Company.objects.filter(
                memberships__user=self.request.user,
                tax_id=normalized,
            )

        return queryset.distinct()


class CompanyDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Detalle, actualización parcial/total y baja lógica de una compañía.

    @version 2.0
    @author Uziel, Agustin
    """

    lookup_field = "id"
    serializer_class = CompanySerializer
    authentication_classes = (SupabaseBearerAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Limita el acceso a compañías con membresía del usuario autenticado.

        @version 1.0
        @author Agustin
        """
        return Company.objects.filter(memberships__user=self.request.user).distinct()

    def get_object(self):
        """Exige owner y Company activa para las operaciones de escritura.

        @version 1.0
        @author Agustin
        """
        company = super().get_object()
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            is_owner = CompanyMember.objects.filter(
                user=self.request.user,
                company=company,
                role__code="owner",
            ).exists()
            if not is_owner or not company.is_active:
                raise PermissionDenied()
        return company

    def perform_destroy(self, instance):
        """
        Desactiva la compañía conservando sus relaciones y datos.

        @version 1.0
        @author Agustin
        """
        instance.is_active = False
        instance.save()

    def handle_exception(self, error):
        from django.http import Http404

        if isinstance(error, Http404):
            return Response(
                {
                    "code": "NEX-COM-004",
                    "message": "Compañía no encontrada.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        if isinstance(error, serializers.ValidationError):
            return Response(
                {
                    "code": "NEX-COM-001",
                    "message": "Los datos enviados no son válidos.",
                    "errors": error.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().handle_exception(error)
