import logging
import uuid

from django.db import DatabaseError
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.cloud.files.api.serializers import FileCreateSerializer
from apps.cloud.files.storage import storage_client
from apps.company.models import CompanyMember


logger = logging.getLogger(__name__)


def check_company_access(company_id, user, write=False):
    """
    Exige membresía y una Company activa para escrituras. 
    @version 1.0
    @author Agustin
    """
    membership = (
        CompanyMember.objects.filter(user=user, company_id=company_id)
        .select_related("company")
        .first()
    )
    if membership is None:
        raise NotFound({"code": "NEX-DOC-002", "message": "Documento no encontrado."})
    if write and not membership.company.is_active:
        raise PermissionDenied()
    return membership.company


def create_file(*, user, data):
    """
    Valida, almacena y registra un archivo mediante las reglas de Cloud.
    @version 1.0
    @author Agustin
    """
    serializer = FileCreateSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    uploaded_file = serializer.validated_data["file"]
    company = check_company_access(
        serializer.validated_data["company_id"], user, write=True
    )
    file_id = uuid.uuid4()
    storage_key = f"{company.id}/{file_id}"
    bucket = storage_client.storage.from_("documents")
    bucket.upload(
        storage_key, uploaded_file.read(), {"content-type": uploaded_file.content_type}
    )
    try:
        return serializer.save(
            id=file_id,
            name=serializer.validated_data.get("name", uploaded_file.name),
            original_name=uploaded_file.name,
            mime_type=uploaded_file.content_type,
            size=uploaded_file.size,
            storage_key=storage_key,
        )
    except DatabaseError:
        cleanup_upload(storage_key)
        raise


def cleanup_upload(storage_key):
    """
    Compensa una carga cuya metadata o asociación no pudo persistirse.
    @version 1.0
    @author Agustin
    """
    try:
        storage_client.storage.from_("documents").remove([storage_key])
    except Exception:
        logger.exception("Supabase Storage cleanup failed for %s.", storage_key)
