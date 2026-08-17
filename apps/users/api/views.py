import logging

from django.db.models import Q
from django.http import Http404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from supabase_auth.errors import AuthApiError

from apps.users import authentication
from apps.users.authentication import SupabaseBearerAuthentication
from apps.users.api.serializers import (
    LoginSerializer,
    RegisterSerializer,
    SystemAdminSerializer,
    UserSerializer,
)
from apps.users.models import User


logger = logging.getLogger(__name__)


def _auth_error(error, code, message, http_status, operation):
    """
    Registra un error de Supabase y crea su respuesta pública.

    @version 1.0
    @param error Excepción devuelta por Supabase Auth.
    @param code Código interno de la respuesta.
    @param message Mensaje público de la respuesta.
    @param http_status Estado HTTP de la respuesta.
    @param operation Operación de autenticación que falló.
    @author Agustin
    """
    logger.exception(
        "[%s] Supabase Auth %s failed (message=%r, code=%r, status=%r).",
        code,
        operation,
        getattr(error, "message", None),
        getattr(error, "code", None),
        getattr(error, "status", None),
    )
    return Response({"code": code, "message": message}, status=http_status)


class UserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    authentication_classes = (SupabaseBearerAuthentication,)

    def initial(self, request, *args, **kwargs):
        """
        Restringe el listado y la búsqueda a administradores del sistema.

        @version 1.0
        @param request: Solicitud HTTP dirigida al ViewSet.
        @author Agustin
        """
        super().initial(request, *args, **kwargs)
        if self.action in {"list", "search"}:
            self._require_system_admin()

    def get_object(self):
        """
        Convierte la ausencia de un usuario en el error público correspondiente.

        @version 1.0
        @author Agustin
        """
        try:
            user = super().get_object()
        except Http404 as error:
            raise NotFound(
                {"code": "NEX-USR-004", "message": "Usuario no encontrado."}
            ) from error
        self._require_user_access(user)
        return user

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

    @action(detail=False, methods=["get"])
    def search(self, request):
        """
        Busca usuarios por nombre, apellido o correo electrónico.

        @version 1.0
        @param request Solicitud que contiene el parámetro de búsqueda.
        @author Agustin
        """
        query = request.query_params.get("q", "").strip()
        if not query:
            raise ValidationError({"q": ["Este parámetro es obligatorio."]})

        users = self.get_queryset().filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
        return Response(self.get_serializer(users, many=True).data)

    @action(detail=True, methods=["post"], url_path="system-admin")
    def system_admin(self, request, pk=None):
        """
        Actualiza el privilegio global de otro usuario.

        @version 1.0
        @param request: Solicitud con el nuevo valor de is_system_admin.
        @param pk: UUID del usuario objetivo.
        @author Agustin
        """
        self._require_system_admin()
        user = self.get_object()
        serializer = SystemAdminSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        is_system_admin = serializer.validated_data["is_system_admin"]
        if user.id == request.user.id and not is_system_admin:
            self._deny_permission()

        user.is_system_admin = is_system_admin
        user.save(update_fields=["is_system_admin"])
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        """
        Activa el perfil local de un usuario.

        @version 1.0
        @param request: Solicitud administrativa autenticada.
        @param pk: UUID del usuario objetivo.
        @author Agustin
        """
        self._require_system_admin()
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active"])
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """
        Desactiva el perfil local de un usuario sin eliminarlo.

        @version 1.0
        @param request: Solicitud administrativa autenticada.
        @param pk: UUID del usuario objetivo.
        @author Agustin
        """
        self._require_system_admin()
        user = self.get_object()
        if user.id == request.user.id:
            self._deny_permission()

        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response(self.get_serializer(user).data)

    def _require_user_access(self, user):
        """
        Permite acceder al perfil propio o a cualquier perfil siendo administrador.

        @version 1.0
        @param user: Perfil local objetivo de la operación.
        @author Agustin
        """
        if self.request.user.is_system_admin or user.id == self.request.user.id:
            return
        self._deny_permission()

    def _require_system_admin(self):
        """
        Exige que el usuario autenticado sea administrador global.

        @version 1.0
        @author Agustin
        """
        if not self.request.user.is_system_admin:
            self._deny_permission()

    @staticmethod
    def _deny_permission():
        """
        Detiene la operación por falta de permisos suficientes.

        @version 1.0
        @author Agustin
        """
        raise PermissionDenied(
            {
                "code": "NEX-USR-011",
                "message": "No fue posible autorizar la operación.",
            }
        )


class RegisterView(APIView):
    def post(self, request):
        """
        Registra una cuenta y crea su perfil local.

        @version 1.0
        @param request Solicitud con email y contraseña del nuevo usuario.
        @author Agustin
        """
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": "NEX-USR-003",
                    "message": "Los datos enviados no son válidos.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_id = authentication.register(**serializer.validated_data).user.id
        except Exception as error:
            if isinstance(error, AuthApiError) and error.status == 429:
                return _auth_error(
                    error,
                    "NEX-USR-007",
                    "Se alcanzó temporalmente el límite de solicitudes. "
                    "Intente nuevamente más tarde.",
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "registration",
                )
            return _auth_error(
                error,
                "NEX-USR-005",
                "No fue posible crear la cuenta.",
                status.HTTP_502_BAD_GATEWAY,
                "registration",
            )

        try:
            user = User.objects.create(
                id=user_id,
                email=serializer.validated_data["email"],
            )
        except Exception:
            return Response(
                {
                    "code": "NEX-USR-006",
                    "message": "No fue posible completar el registro.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"id": str(user.id)}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    def post(self, request):
        """
        Inicia sesión y devuelve la sesión válida del usuario.

        @version 1.0
        @param request Solicitud con email y contraseña.
        @author Agustin
        """
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": "NEX-USR-003",
                    "message": "Los datos enviados no son válidos.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = authentication.login(**serializer.validated_data)
            auth_user = result.user
            session = result.session
            if not auth_user or not session:
                raise ValueError("Supabase Auth did not return a valid session.")
            if not all(
                (session.access_token, session.refresh_token, session.token_type)
            ) or session.expires_in is None:
                raise ValueError("Supabase Auth did not return a valid session.")
            user_id = auth_user.id
            tokens = {
                "id": str(user_id),
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
                "expires_in": session.expires_in,
                "token_type": session.token_type,
            }
        except Exception as error:
            if isinstance(error, AuthApiError):
                if error.status == 429:
                    return _auth_error(
                        error,
                        "NEX-USR-007",
                        "Se alcanzó temporalmente el límite de solicitudes. "
                        "Intente nuevamente más tarde.",
                        status.HTTP_429_TOO_MANY_REQUESTS,
                        "login",
                    )
                if error.code == "invalid_credentials":
                    return _auth_error(
                        error,
                        "NEX-USR-008",
                        "Email o contraseña incorrectos.",
                        status.HTTP_401_UNAUTHORIZED,
                        "login",
                    )
            return _auth_error(
                error,
                "NEX-USR-009",
                "No fue posible iniciar sesión.",
                status.HTTP_502_BAD_GATEWAY,
                "login",
            )

        user = User.objects.filter(id=user_id).first()
        if user is None:
            return Response(
                {
                    "code": "NEX-USR-001",
                    "message": "No fue posible autorizar la operación.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if not user.is_active:
            return Response(
                {
                    "code": "NEX-USR-002",
                    "message": "No fue posible autorizar la operación.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(tokens)
