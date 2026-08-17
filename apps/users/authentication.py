from django.conf import settings
from django.db import DatabaseError
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import APIException, AuthenticationFailed, PermissionDenied
from supabase import create_client

from apps.users.models import User


supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


class SupabaseBearerAuthentication(BaseAuthentication):
    """
    Autentica requests mediante un JWT Bearer emitido por Supabase Auth.

    @version 1.0
    @author Agustin
    """

    def authenticate(self, request):
        """
        Valida el token y devuelve el perfil local activo del usuario.

        @version 1.0
        @param request: Solicitud HTTP autenticada mediante Bearer.
        @author Agustin
        """
        token = self._get_bearer_token(request)

        try:
            response = supabase.auth.get_user(token)
            auth_user = response.user if response else None
            if not auth_user:
                raise ValueError("Supabase Auth did not return a user.")
        except Exception as error:
            raise self._authentication_error() from error

        try:
            user = User.objects.filter(id=auth_user.id).first()
        except DatabaseError as error:
            raise APIException(
                {
                    "code": "NEX-USR-012",
                    "message": "Error interno al validar el perfil del usuario autenticado.",
                }
            ) from error

        if user is None:
            raise PermissionDenied(
                {
                    "code": "NEX-USR-001",
                    "message": "No fue posible autorizar la operación.",
                }
            )
        if not user.is_active:
            raise PermissionDenied(
                {
                    "code": "NEX-USR-002",
                    "message": "No fue posible autorizar la operación.",
                }
            )

        return user, token

    def authenticate_header(self, request):
        """
        Indica el esquema de autenticación requerido por la API.

        @version 1.0
        @param request: Solicitud HTTP sin autenticar.
        @author Agustin
        """
        return "Bearer"

    def _get_bearer_token(self, request):
        """
        Extrae un token Bearer del header Authorization.

        @version 1.0
        @param request: Solicitud HTTP que contiene el header Authorization.
        @author Agustin
        """
        authorization = get_authorization_header(request).split()
        if len(authorization) != 2 or authorization[0].lower() != b"bearer":
            raise self._authentication_error()

        try:
            return authorization[1].decode("utf-8")
        except UnicodeDecodeError as error:
            raise self._authentication_error() from error

    @staticmethod
    def _authentication_error():
        """
        Construye la respuesta uniforme para fallos de autenticación.

        @version 1.0
        @author Agustin
        """
        return AuthenticationFailed(
            {
                "code": "NEX-USR-010",
                "message": "No fue posible autenticar la solicitud.",
            }
        )


def register(email, password):
    """
    Registra un usuario mediante Supabase Auth.

    @version 1.0
    @param email Correo electrónico utilizado para crear la cuenta.
    @param password Contraseña utilizada para crear la cuenta.
    @author Agustin
    """
    return supabase.auth.sign_up({"email": email, "password": password})


def login(email, password):
    """
    Inicia sesión mediante Supabase Auth.

    @version 1.0
    @param email Correo electrónico de la cuenta.
    @param password Contraseña de la cuenta.
    @author Agustin
    """
    return supabase.auth.sign_in_with_password({"email": email, "password": password})
