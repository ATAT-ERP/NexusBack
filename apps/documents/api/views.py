import logging
import uuid

import httpx
from django.conf import settings
from django.db import DatabaseError
from django.db.models import Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from storage3.exceptions import StorageException

from apps.company.models import CompanyMember
from apps.documents.api.serializers import (
    CompanyQuery,
    DocumentCreateSerializer,
    DocumentSerializer,
    ListQuerySerializer,
)
from apps.documents.models import Document
from apps.documents.storage import storage_client
from apps.users.authentication import SupabaseBearerAuthentication


logger = logging.getLogger(__name__)
SIGNED_URL_EXPIRATION_SECONDS = 60


class DocumentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Crea, lista y actualiza la metadata de documentos restringida a una Company.

    @version 2.1
    @author Agustin
    """

    serializer_class = DocumentSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_authenticators(self):
        """
        Exige un Bearer de Supabase para crear, listar o descargar documentos.

        @version 1.2
        @author Agustin
        """
        if self.action in ("create", "list", "download"):
            return [SupabaseBearerAuthentication()]
        return []

    def get_permissions(self):
        """
        Exige un usuario autenticado para crear, listar o descargar documentos.

        @version 1.2
        @author Agustin
        """
        if self.action in ("create", "list", "download"):
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
        Sube el archivo, persiste su metadata y limpia Storage si falla la base.

        @version 1.1
        @author Agustin
        """
        uploaded_file = serializer.validated_data["file"]
        company = serializer.validated_data["company"]
        document_id = uuid.uuid4()
        storage_key = f"{company.id}/{document_id}"
        mime_type = uploaded_file.content_type
        bucket = storage_client.storage.from_("documents")

        bucket.upload(
            storage_key,
            uploaded_file.read(),
            {"content-type": mime_type},
        )
        try:
            return serializer.save(
                id=document_id,
                name=serializer.validated_data.get("name", uploaded_file.name),
                original_name=uploaded_file.name,
                mime_type=mime_type,
                size=uploaded_file.size,
                storage_key=storage_key,
            )
        except DatabaseError:
            try:
                bucket.remove([storage_key])
            except Exception:
                logger.exception("Supabase Storage cleanup failed for document %s.", document_id)
            raise

    def get_object(self):
        """
        Obtiene un documento; para download no confía en una Company enviada por cliente.

        @version 1.1
        @author Agustin
        """
        try:
            document_id = uuid.UUID(self.kwargs["pk"])
        except (TypeError, ValueError):
            self._not_found()

        try:
            if self.action == "download":
                return get_object_or_404(Document, id=document_id)

            query_serializer = CompanyQuery(data=self.request.query_params)
            query_serializer.is_valid(raise_exception=True)
            return get_object_or_404(
                Document,
                id=document_id,
                company_id=query_serializer.validated_data["company_id"],
            )
        except Http404:
            self._not_found()

    def handle_exception(self, error):
        """
        Normaliza los errores de validación y Storage de la API de documentos.

        @version 1.1
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
        if isinstance(error, (StorageException, httpx.RequestError)):
            if self.action == "download":
                logger.exception("[NEX-DOC-004] Supabase Storage signed URL creation failed.")
                return Response(
                    {
                        "code": "NEX-DOC-004",
                        "message": "No fue posible preparar la descarga del documento.",
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            logger.exception("[NEX-DOC-003] Supabase Storage upload failed.")
            return Response(
                {
                    "code": "NEX-DOC-003",
                    "message": "No fue posible almacenar el documento.",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return super().handle_exception(error)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, *args, **kwargs):
        """
        Genera una URL temporal para descargar un documento de la Company autorizada.

        @version 1.0
        @author Agustin
        """
        document = self.get_object()
        if not CompanyMember.objects.filter(
            user=request.user,
            company_id=document.company_id,
        ).exists():
            raise PermissionDenied()

        signed_url = storage_client.storage.from_("documents").create_signed_url(
            document.storage_key,
            SIGNED_URL_EXPIRATION_SECONDS,
            {"download": document.original_name},
        )["signedURL"]
        return Response({"url": signed_url})

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
        Construye el listado de la Company a la que pertenece el usuario.

        @version 1.1
        @author Agustin
        """
        query_serializer = ListQuerySerializer(data=self.request.query_params)
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data

        if not CompanyMember.objects.filter(
            user=self.request.user,
            company_id=filters["company_id"],
        ).exists():
            raise PermissionDenied()

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