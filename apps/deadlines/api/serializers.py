from rest_framework import serializers

from apps.company.models import Company
from apps.deadlines.models import Deadline


class DeadlineSerializer(serializers.ModelSerializer):
    """
    Serializa tareas y restringe la compañía a las activas del usuario.
    @version 1.0
    @author Agustin
    """

    class Meta:
        model = Deadline
        fields = (
            "id", "owner", "company", "name", "period", "due_date", "status",
            "notes", "created_at", "updated_at",
        )
        read_only_fields = ("id", "owner", "created_at", "updated_at")

    def get_fields(self):
        """Limita las compañías de escritura a las membresías activas. @version 1.0"""
        fields = super().get_fields()
        fields["company"].queryset = Company.objects.filter(
            memberships__user=self.context["request"].user, is_active=True
        )
        return fields
