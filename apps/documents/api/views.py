import uuid

from django.conf import settings
from django.db.models import Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from apps.documents.api.serializers import (
    CompanyQuery,
    ListQuerySerializer,
    MetadataSerializer,
    UpdateSerializer,
)
from apps.documents.models import Document


class DocumentViewSet(
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Lista y actualiza la metadata de documentos restringida a una Company.

    @version 1.0
    @author Agustin
    """

    serializer_class = MetadataSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_serializer_class(self):
        """
        Usa el serializer de escritura para las actualizaciones parciales.

        @version 1.0
        @author Agustin
        """
        if self.action == "partial_update":
            return UpdateSerializer
        return super().get_serializer_class()

    def get_object(self):
        """
        Obtiene un documento dentro de la Company indicada sin revelar otros registros.

        @version 1.0
        @author Agustin
        """
        query_serializer = CompanyQuery(data=self.request.query_params)
        query_serializer.is_valid(raise_exception=True)

        try:
            document_id = uuid.UUID(self.kwargs["pk"])
        except (TypeError, ValueError):
            self._not_found()

        try:
            return get_object_or_404(
                Document,
                id=document_id,
                company_id=query_serializer.validated_data["company_id"],
            )
        except Http404:
            self._not_found()

    def handle_exception(self, error):
        """
        Normaliza los errores de validación de la API de documentos.

        @version 1.0
        @param error Excepción capturada durante la solicitud.
        @author Agustin
        """
        if isinstance(error, ValidationError):
            return Response(
                {
                    "code": "NEX-DOC-001",
                    "message": "Los datos enviados no son válidos.",
                    "errors": error.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().handle_exception(error)

    @action(detail=False, methods=["get"])
    def usage(self, request):
        """
        Devuelve el uso y espacio disponible de documentos para una Company.

        @version 1.0
        @author Agustin
        """
        query = CompanyQuery(data=request.query_params)
        query.is_valid(raise_exception=True)

        used = (
            Document.objects.filter(company_id=query.validated_data["company_id"])
            .aggregate(used=Sum("size"))["used"]
            or 0
        )
        limit = settings.DOCUMENT_COMPANY_LIMIT_BYTES
        return Response(
            {
                "used": used,
                "limit": limit,
                "available": max(limit - used, 0),
            }
        )

    def get_queryset(self):
        """
        Construye el listado filtrado por Company, categoría y búsqueda opcional.

        @version 1.0
        @author Agustin
        """
        query_serializer = ListQuerySerializer(data=self.request.query_params)
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data

        documents = Document.objects.filter(company_id=filters["company_id"])
        category_id = filters.get("category_id")
        if category_id is not None:
            documents = documents.filter(category_id=category_id)

        search = filters.get("q", "")
        if search:
            documents = documents.filter(
                Q(name__icontains=search) | Q(original_name__icontains=search)
            )

        return documents.order_by("-created_at")

    @staticmethod
    def _not_found():
        """
        Detiene la operación con la respuesta pública de documento no encontrado.

        @version 1.0
        @author Agustin
        """
        raise NotFound(
            {"code": "NEX-DOC-002", "message": "Documento no encontrado."}
        )
