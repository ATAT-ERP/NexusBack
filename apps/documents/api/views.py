from django.db.models import Q
from rest_framework import mixins, viewsets

from apps.documents.api.serializers import (
    DocumentListQuerySerializer,
    DocumentSerializer,
)
from apps.documents.models import Document


class DocumentViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Lista la metadata de documentos restringida a una Company.

    @version 1.0
    @author Agustin
    """

    serializer_class = DocumentSerializer

    def get_queryset(self):
        """
        Construye el listado filtrado por Company, categoría y búsqueda opcional.

        @version 1.0
        @author Agustin
        """
        query_serializer = DocumentListQuerySerializer(data=self.request.query_params)
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
