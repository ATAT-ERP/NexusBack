import uuid

from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets

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
            raise Http404

        return get_object_or_404(
            Document,
            id=document_id,
            company_id=query_serializer.validated_data["company_id"],
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
