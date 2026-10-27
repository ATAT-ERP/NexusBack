import logging

import httpx
from django.db import DatabaseError
from django.shortcuts import get_object_or_404
from django.urls import reverse
from reportlab.platypus.doctemplate import LayoutError
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView
from storage3.exceptions import StorageException

from apps.billing.models import CreditNote, Invoice
from apps.billing.services.representation import get_representation, validate_representable
from apps.billing.views.point_of_sale import CompanyScopedBillingView
from apps.cloud.files.api.serializers import FileSerializer


logger = logging.getLogger(__name__)


class InvoiceRepresentationView(CompanyScopedBillingView, APIView):
    """Consulta o solicita el File de un comprobante de la Company autorizada.

    @version 1.0
    """

    model = Invoice

    def get_object(self):
        """Obtiene el comprobante dentro del perfil fiscal autorizado. @version 1.0"""
        return get_object_or_404(
            self.model.objects.select_related("representation_file"),
            pk=self.kwargs["pk"],
            point_of_sale__fiscal_profile=self.get_fiscal_profile(),
        )

    def get(self, request, *args, **kwargs):
        """Consulta el archivo asociado sin generarlo ni acceder a Storage. @version 1.0"""
        document = self.get_object()
        validate_representable(document)
        if not document.representation_file_id:
            raise NotFound("El comprobante todavía no tiene representación.")
        return self.file_response(document.representation_file)

    def post(self, request, *args, **kwargs):
        """Genera o reutiliza la representación independientemente de la emisión. @version 1.0"""
        file, created = get_representation(self.get_object(), request.user)
        return self.file_response(file, status=201 if created else 200)

    @staticmethod
    def file_response(file, status=200):
        """Expone metadata de Cloud y su ruta de descarga protegida. @version 1.0"""
        return Response(
            {
                "file": FileSerializer(file).data,
                "download_url": reverse("file-download", kwargs={"pk": file.pk}),
            },
            status=status,
        )

    def handle_exception(self, error):
        """Separa fallos de almacenamiento y generación de la emisión. @version 1.0"""
        if isinstance(error, (StorageException, httpx.RequestError)):
            logger.exception("[NEX-DOC-003] Representation storage failed.")
            return Response(
                {"code": "NEX-DOC-003", "message": "No fue posible almacenar el documento."},
                status=502,
            )
        if isinstance(error, (LayoutError, ValueError, DatabaseError)):
            logger.exception("[NEX-BIL-001] Representation generation or association failed.")
            return Response(
                {"code": "NEX-BIL-001", "message": "No fue posible generar la representación."},
                status=500,
            )
        return super().handle_exception(error)


class CreditNoteRepresentationView(InvoiceRepresentationView):
    """Reutiliza el flujo de representación para Notas de Crédito. @version 1.0"""

    model = CreditNote
