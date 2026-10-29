from datetime import timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone
from django.utils.functional import cached_property
from rest_framework import serializers

from apps.company.models import Company
from apps.deadlines.models import Deadline


class DeadlineFilterSerializer(serializers.Serializer):
    """
    Valida los filtros opcionales de la agenda. 
    @version 1.0
    @author Agustin
    """

    company_id = serializers.UUIDField(required=False)
    status = serializers.ChoiceField(choices=Deadline.Status.choices, required=False)
    due_date_from = serializers.DateField(required=False)
    due_date_to = serializers.DateField(required=False)

    def validate(self, attrs):
        """
        Rechaza un rango de vencimientos invertido. 
        @version 1.0
        @author Agustin
        """
        start = attrs.get("due_date_from")
        end = attrs.get("due_date_to")
        if start and end and start > end:
            raise serializers.ValidationError(
                {"due_date_to": "La fecha final debe ser igual o posterior a la inicial."}
            )
        return attrs


class DeadlineSerializer(serializers.ModelSerializer):
    """
    Serializa tareas y restringe la compañía a las activas del usuario.
    @version 1.1
    @author Agustin
    """
    overdue = serializers.SerializerMethodField()
    due_soon = serializers.SerializerMethodField()

    class Meta:
        model = Deadline
        fields = (
            "id", "owner", "company", "name", "period", "due_date", "status",
            "notes", "created_at", "updated_at", "overdue", "due_soon",
        )
        read_only_fields = ("id", "owner", "created_at", "updated_at")

    @cached_property
    def business_date(self):
        """
        Obtiene la fecha de Argentina para toda la respuesta. 
        @version 1.0
        @author Agustin
        """
        return timezone.localdate(timezone=ZoneInfo("America/Argentina/Buenos_Aires"))

    def get_overdue(self, deadline):
        """
        Indica si una tarea pendiente ya venció. 
        @version 1.0
        @author Agustin
        """
        return deadline.status == Deadline.Status.PENDING and deadline.due_date < self.business_date

    def get_due_soon(self, deadline):
        """
        Indica si una tarea pendiente vence dentro de siete días. 
        @version 1.0
        @author Agustin
        """
        return (
            deadline.status == Deadline.Status.PENDING
            and self.business_date <= deadline.due_date <= self.business_date + timedelta(days=7)
        )

    def get_fields(self):
        """
        Limita las compañías de escritura a las membresías activas. 
        @version 1.0
        @author Agustin
        """
        fields = super().get_fields()
        fields["company"].queryset = Company.objects.filter(
            memberships__user=self.context["request"].user, is_active=True
        )
        return fields
