from django.http import Http404
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from apps.users.api.serializers import UserSerializer
from apps.users.models import User


class UserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_object(self):
        """
        Convierte la ausencia de un usuario en el error público correspondiente.

        @version 1.0
        @author Agustin
        """
        try:
            return super().get_object()
        except Http404 as error:
            raise NotFound(
                {"code": "NEX-USR-004", "message": "Usuario no encontrado."}
            ) from error

    def handle_exception(self, error):
        """
        Normaliza los errores de validación de la API de usuarios.

        @version 1.0
        @param error Excepción capturada durante la solicitud.
        @author Agustin
        """
        if isinstance(error, ValidationError):
            return Response(
                {
                    "code": "NEX-USR-003",
                    "message": "Los datos enviados no son válidos.",
                    "errors": error.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().handle_exception(error)
