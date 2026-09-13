from rest_framework import serializers

from apps.company.models import Company
from apps.documents.models import Document


class DocumentSerializer(serializers.ModelSerializer):
    """
    Expone la metadata pública de un documento sin revelar su clave de almacenamiento.

    @version 1.0
    @author Agustin
    """

    company_id = serializers.UUIDField(read_only=True)

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


class DocumentCreateSerializer(serializers.ModelSerializer):
    """
    Valida los datos necesarios para crear un documento desde un archivo recibido.

    @version 1.0
    @author Agustin
    """

    company_id = serializers.PrimaryKeyRelatedField(
        source="company",
        queryset=Company.objects.all(),
    )
    file = serializers.FileField(write_only=True)

    class Meta:
        model = Document
        fields = (
            "id",
            "company_id",
            "file",
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
            "original_name",
            "mime_type",
            "size",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {"name": {"required": False}}

    def create(self, validated_data):
        """
        Persiste la metadata sin incluir el archivo, que ya fue enviado a Storage.

        @version 1.0
        @author Agustin
        """
        validated_data.pop("file")
        return super().create(validated_data)


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
