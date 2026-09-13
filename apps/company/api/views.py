import re

from django.db import transaction
from django.db.models import Q
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.company.api.serializers import CompanySerializer
from apps.company.models import Company, CompanyMember, CompanyRole, normalize_tax_id
from apps.users.authentication import SupabaseBearerAuthentication

class CompanyListView(generics.ListCreateAPIView):
    """
    Lista compañías registradas y permite dar de alta una nueva.

    @version 1.0
    @author Antonio
    @author Uziel
    """

    serializer_class = CompanySerializer

    def get_authenticators(self):
        if self.request.method == "POST":
            return [SupabaseBearerAuthentication()]
        return []

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return super().get_permissions()

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
        Retorna compañías filtradas por estado. Por defecto solo activas.

        @version 1.0
        @author Uziel
        """
        is_active = self.request.query_params.get("is_active", "true").lower()

        if is_active == "all":
            return Company.objects.all()

        if is_active == "false":
            return Company.objects.filter(is_active=False)

        # Caso por defecto: solo activas
        return Company.objects.filter(is_active=True)

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

    @version 1.0
    @author Antonio
    """

    serializer_class = CompanySerializer

    def get_queryset(self):
        raw_query = self.request.query_params.get("q", "")
        query = re.sub(r"\s+", " ", raw_query).strip()
        if not query:
            return Company.objects.none()

        queryset = Company.objects.filter(
            Q(name__icontains=query) | Q(legal_name__icontains=query)
        )

        normalized = normalize_tax_id(query)
        if normalized and normalized.isdigit():
            queryset = queryset | Company.objects.filter(tax_id=normalized)

        return queryset.distinct()


class CompanyDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Detalle, actualización parcial/total y baja lógica de una compañía.

    @version 1.0
    @author Uziel
    """

    queryset = Company.objects.all()
    lookup_field = "id"

    serializer_class = CompanySerializer

    def perform_destroy(self, instance):
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
