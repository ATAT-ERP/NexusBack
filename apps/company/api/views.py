import logging
import re

from django.db.models import Q
from rest_framework import generics, serializers, status
from rest_framework.response import Response

from apps.company.api.serializers import (
    CompanyCreateSerializer,
    CompanySerializer,
    CompanyUpdateSerializer,
)
from apps.company.models import Company, normalize_tax_id


logger = logging.getLogger(__name__)


class CompanyListView(generics.ListCreateAPIView):
    pagination_class = None

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CompanyCreateSerializer
        return CompanySerializer

    def get_queryset(self):
        queryset = Company.objects.all()
        
        is_active_param = self.request.query_params.get("is_active", "true").lower()
        if is_active_param == "true":
            queryset = queryset.filter(is_active=True)
        elif is_active_param == "false":
            queryset = queryset.filter(is_active=False)
        elif is_active_param == "all":
            pass
        else:
            queryset = queryset.filter(is_active=True)
        
        return queryset

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


class CompanyCreateView(generics.CreateAPIView):
    serializer_class = CompanyCreateSerializer

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
    serializer_class = CompanySerializer
    pagination_class = None

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
    queryset = Company.objects.all()
    lookup_field = "id"

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return CompanyUpdateSerializer
        return CompanySerializer

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
