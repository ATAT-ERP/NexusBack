import uuid

from django.conf import settings
from django.db.models import Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.documents.api.serializers import (
    CompanyQuery,
    DocumentCreateSerializer,
    DocumentSerializer,
    ListQuerySerializer,
)
from apps.documents.models import Document
from apps.documents.storage import storage_client
from apps.users.authentication import SupabaseBearerAuthentication


class DocumentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Crea, lista y actualiza la metadata de documentos restringida a una Company.

    @version 2.0
    @author Agustin
    """

    serializer_class = DocumentSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_authenticators(self):
        """
        Exige un Bearer de Supabase para crear documentos.

        @version 1.0
        @author Agustin
        """
        if self.request.method == "POST":
            return [SupabaseBearerAuthentication()]
        return []

    def get_permissions(self):
        """
        Exige un usuario autenticado para crear documentos.

        @version 1.0
        @author Agustin
        """
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_serializer_class(self):
        """
        Usa el serializer de entrada multipart únicamente durante la creación.

        @version 1.0
        @author Agustin
        """
        if self.request.method == "POST":
            return DocumentCreateSerializer
        return DocumentSerializer

    def create(self, request, *args, **kwargs):
        """
        Crea un documento y responde con su metadata pública.

        @version 1.0
        @author Agustin
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = self.perform_create(serializer)
        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        """
        Sube el archivo y persiste la metadata con la clave física definitiva.

        @version 1.0
        @author Agustin
        """
        uploaded_file = serializer.validated_data["file"]
        company = serializer.validated_data["company"]
        document_id = uuid.uuid4()
        storage_key = f"{company.id}/{document_id}"
        mime_type = uploaded_file.content_type or "application/octet-stream"

        storage_client.storage.from_("documents").upload(
            storage_key,
            uploaded_file.read(),
            {"content-type": mime_type},
        )
        return serializer.save(
            id=document_id,
            name=serializer.validated_data.get("name", uploaded_file.name),
            original_name=uploaded_file.name,
            mime_type=mime_type,
            size=uploaded_file.size,
            storage_key=storage_key,
        )

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
