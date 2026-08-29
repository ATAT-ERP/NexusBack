import logging
import re

from django.db.models import Q
from rest_framework import generics, serializers, status
from rest_framework.response import Response

from apps.company.api.serializers import CompanyCreateSerializer, CompanySerializer
from apps.company.models import Company, normalize_tax_id


logger = logging.getLogger(__name__)


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
