from rest_framework import serializers

from apps.documents.models import Document


class MetadataSerializer(serializers.ModelSerializer):
    """
    Expone la metadata pública de un documento sin revelar su clave de almacenamiento.

    @version 1.0
    @author Agustin
    """

    class Meta:
        model = Document
        fields = (
            "id",
            "company_id",
            "name",
            "original_name",
            "mime_type",
            "size",
            "category_id",
            "created_at",
            "updated_at",
        )


class CompanyQuery(serializers.Serializer):
    """
    Valida la Company requerida para operar sobre documentos.

    @version 1.0
    @author Agustin
    """

    company_id = serializers.UUIDField()


class ListQuerySerializer(CompanyQuery):
    """
    Valida los filtros admitidos para el listado de documentos de una Company.

    @version 1.0
    @author Agustin
    """

    q = serializers.CharField(required=False, allow_blank=True)
    category_id = serializers.UUIDField(required=False)


class UpdateSerializer(serializers.ModelSerializer):
    """
    Actualiza la metadata editable y expone la representación pública del documento.

    @version 1.0
    @author Agustin
    """

    class Meta:
        model = Document
        fields = (
            "id",
            "company_id",
            "name",
            "original_name",
            "mime_type",
            "size",
            "category_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "company_id",
            "original_name",
            "mime_type",
            "size",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {
            "name": {"required": False, "trim_whitespace": True},
            "category_id": {"required": False, "allow_null": True},
        }
