from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from apps.deadlines.api.serializers import DeadlineSerializer
from apps.deadlines.models import Deadline
from apps.users.authentication import SupabaseBearerAuthentication


class DeadlineListView(generics.ListCreateAPIView):
    """
    Lista y crea tareas privadas del usuario autenticado. 
    @version 1.0
    @author Agustin
    """
    serializer_class = DeadlineSerializer
    authentication_classes = (SupabaseBearerAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """
        Limita las tareas a su propietario y a membresías vigentes. 
        @version 1.0
        @author Agustin
        """
        return Deadline.objects.filter(
            owner=self.request.user, company__memberships__user=self.request.user
        ).select_related("company")

    def perform_create(self, serializer):
        """
        Asigna el propietario autenticado a la tarea. 
        @version 1.0
        @author Agustin
        """
        serializer.save(owner=self.request.user)


class DeadlineDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Consulta y modifica una tarea privada del usuario. 
    @version 1.0
    @author Agustin
    """

    serializer_class = DeadlineSerializer
    authentication_classes = (SupabaseBearerAuthentication,)
    permission_classes = (IsAuthenticated,)
    lookup_field = "id"

    def get_queryset(self):
        """
        Limita las tareas a su propietario y a membresías vigentes. 
        @version 1.0
        @author Agustin
        """
        return Deadline.objects.filter(
            owner=self.request.user, company__memberships__user=self.request.user
        ).select_related("company")

    def get_object(self):
        """
        Impide modificar tareas de compañías inactivas. 
        @version 1.0
        @author Agustin
        """
        deadline = super().get_object()
        if self.request.method in ("PUT", "PATCH", "DELETE") and not deadline.company.is_active:
            raise PermissionDenied()
        return deadline
