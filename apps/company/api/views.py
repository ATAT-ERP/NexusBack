import re

from django.db import IntegrityError, transaction
from django.db.models import F, Q
from rest_framework import generics, serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.company.api.serializers import (
    CompanyMemberCreateSerializer,
    CompanyMemberSerializer,
    CompanySerializer,
    CompanyMemberRoleSerializer,
)
from apps.company.models import Company, CompanyMember, CompanyRole, normalize_tax_id
from apps.users.authentication import SupabaseBearerAuthentication
from apps.users.models import User


def filter_company_queryset(queryset, query_params):
    """
    Aplica los filtros públicos de estado y tipo a una consulta de Companies.

    @version 1.0
    @author Agustin
    """
    is_active = query_params.get("is_active", "true").lower()
    if is_active == "true":
        queryset = queryset.filter(is_active=True)
    elif is_active == "false":
        queryset = queryset.filter(is_active=False)
    elif is_active != "all":
        raise serializers.ValidationError(
            {"is_active": "Use 'true', 'false' o 'all'."}
        )

    if "type" in query_params:
        company_type = query_params["type"]
        if company_type not in Company.Type.values:
            raise serializers.ValidationError(
                {"type": "Tipo de compañía inválido."}
            )
        queryset = queryset.filter(type=company_type)

    return queryset


class CompanyListView(generics.ListCreateAPIView):
    """
    Lista compañías registradas y permite dar de alta una nueva.

    @version 2.0
    @author Agustin, Antonio, Uziel
    """

    serializer_class = CompanySerializer
    authentication_classes = (SupabaseBearerAuthentication,)
    permission_classes = (IsAuthenticated,)

    def perform_create(self, serializer):
        """
        Crea una compañía y asigna al usuario creador como owner.

        @version 1.1
        @author Agustin
        """
        with transaction.atomic():
            company = serializer.save()
            owner_role = CompanyRole.objects.get(code="owner")
            CompanyMember.objects.create(
                user=self.request.user,
                company=company,
                role=owner_role,
            )
            company.my_role = owner_role.code

    def get_queryset(self):
        """
        Retorna compañías del usuario filtradas por estado. Por defecto solo activas.

        @version 1.2
        @author Uziel, Agustin
        """
        companies = Company.objects.filter(
            memberships__user=self.request.user,
        ).annotate(my_role=F("memberships__role__code"))
        return filter_company_queryset(
            companies, self.request.query_params
        ).distinct()

    def handle_exception(self, error):
        if isinstance(error, serializers.ValidationError):
            return Response(
                {
                    "code": "NEX-COM-001",
                    "message": "Los datos enviados no son válidos.",
                    "errors": error.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().handle_exception(error)


class CompanySearchView(generics.ListAPIView):
    """
    Búsqueda de compañías por nombre, razón social o CUIT.

    @version 2.1
    @author Antonio
    """

    serializer_class = CompanySerializer
    authentication_classes = (SupabaseBearerAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """
        Busca Companies propias aplicando texto, estado y tipo.

        @version 2.0
        @author Antonio, Agustin
        """
        raw_query = self.request.query_params.get("q", "")
        query = re.sub(r"\s+", " ", raw_query).strip()
        queryset = Company.objects.filter(
            memberships__user=self.request.user,
        ).annotate(my_role=F("memberships__role__code"))

        queryset = filter_company_queryset(queryset, self.request.query_params)
        if not query:
            return queryset.none()

        search_filter = Q(name__icontains=query) | Q(legal_name__icontains=query)
        normalized = normalize_tax_id(query)
        if normalized and normalized.isdigit():
            search_filter |= Q(tax_id=normalized)

        return queryset.filter(search_filter).distinct()

    def handle_exception(self, error):
        """
        Mantiene el formato de error Company para parámetros inválidos.

        @version 1.0
        @author Agustin
        """
        if isinstance(error, serializers.ValidationError):
            return Response(
                {
                    "code": "NEX-COM-001",
                    "message": "Los datos enviados no son válidos.",
                    "errors": error.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().handle_exception(error)


class CompanyDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Detalle, actualización parcial/total y baja lógica de una compañía.

    @version 2.0
    @author Uziel, Agustin
    """

    lookup_field = "id"
    serializer_class = CompanySerializer
    authentication_classes = (SupabaseBearerAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Limita el acceso a compañías con membresía del usuario autenticado.

        @version 1.1
        @author Agustin
        """
        return Company.objects.filter(
            memberships__user=self.request.user,
        ).annotate(my_role=F("memberships__role__code")).distinct()

    def get_object(self):
        """Exige owner y Company activa para las operaciones de escritura.

        @version 1.0
        @author Agustin
        """
        company = super().get_object()
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            is_owner = CompanyMember.objects.filter(
                user=self.request.user,
                company=company,
                role__code="owner",
            ).exists()
            if not is_owner or not company.is_active:
                raise PermissionDenied()
        return company

    def perform_destroy(self, instance):
        """
        Desactiva la compañía conservando sus relaciones y datos.

        @version 1.0
        @author Agustin
        """
        instance.is_active = False
        instance.save()

    def handle_exception(self, error):
        from django.http import Http404

        if isinstance(error, Http404):
            return Response(
                {
                    "code": "NEX-COM-004",
                    "message": "Compañía no encontrada.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        if isinstance(error, serializers.ValidationError):
            return Response(
                {
                    "code": "NEX-COM-001",
                    "message": "Los datos enviados no son válidos.",
                    "errors": error.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().handle_exception(error)


class CompanyMembersBaseView(APIView):
    """
    Comparte autenticación, acceso y errores de las operaciones de membresía.

    @version 1.0
    @author Agustin
    """

    authentication_classes = (SupabaseBearerAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_company(self, company_id, lock=False):
        """
        Obtiene una Company visible para el usuario y opcionalmente la bloquea.

        @version 1.0
        @author Agustin
        """
        if lock:
            company = Company.objects.select_for_update().filter(pk=company_id).first()
        else:
            company = Company.objects.filter(
                pk=company_id,
                memberships__user=self.request.user,
            ).first()

        if company is None:
            raise NotFound(
                {"code": "NEX-COM-004", "message": "Compañía no encontrada."}
            )
        if lock and not CompanyMember.objects.filter(
            company=company,
            user=self.request.user,
        ).exists():
            raise NotFound(
                {"code": "NEX-COM-004", "message": "Compañía no encontrada."}
            )
        return company

    def require_owner(self, company):
        """
        Exige el rol owner para administrar miembros de una Company.

        @version 1.0
        @author Agustin
        """
        if not CompanyMember.objects.filter(
            company=company,
            user=self.request.user,
            role__code="owner",
        ).exists():
            raise PermissionDenied()
        if not company.is_active:
            raise PermissionDenied()

    def handle_exception(self, error):
        """
        Conserva los códigos públicos existentes de Company.

        @version 1.0
        @author Agustin
        """
        if isinstance(error, serializers.ValidationError):
            return Response(
                {
                    "code": "NEX-COM-001",
                    "message": "Los datos enviados no son válidos.",
                    "errors": error.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().handle_exception(error)


class CompanyMembersView(CompanyMembersBaseView):
    """
    Consulta y agrega usuarios a una Company.

    @version 1.1
    @author Agustin
    """

    def get(self, request, id):
        """
        Lista miembros con sus datos de identificación y rol.

        @version 1.0
        @author Agustin
        """
        company = self.get_company(id)
        memberships = CompanyMember.objects.filter(company=company).select_related(
            "user", "role"
        )
        return Response(CompanyMemberSerializer(memberships, many=True).data)

    def post(self, request, id):
        """
        Asocia un usuario existente por UUID o correo con un rol registrado.

        @version 1.1
        @author Agustin
        """
        try:
            with transaction.atomic():
                company = self.get_company(id, lock=True)
                self.require_owner(company)
                serializer = CompanyMemberCreateSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                data = serializer.validated_data
                identifier_field = "email" if "email" in data else "user_id"
                if identifier_field == "email":
                    candidates = list(
                        User.objects.filter(email__iexact=data["email"])
                        .order_by("pk")[:2]
                    )
                    user = candidates[0] if len(candidates) == 1 else None
                else:
                    user = User.objects.filter(pk=data["user_id"]).first()

                if (
                    user is None
                    or not user.is_active
                    or CompanyMember.objects.filter(
                        company=company,
                        user=user,
                    ).exists()
                ):
                    raise serializers.ValidationError(
                        {identifier_field: "No se pudo asociar el usuario."}
                    )
                membership = CompanyMember.objects.create(
                    company=company,
                    user=user,
                    role=data["role"],
                )
                membership = CompanyMember.objects.select_related(
                    "user", "role"
                ).get(pk=membership.pk)
        except IntegrityError as error:
            identifier_field = (
                "email" if "email" in request.data else "user_id"
            )
            raise serializers.ValidationError(
                {identifier_field: "No se pudo asociar el usuario."}
            ) from error

        return Response(
            CompanyMemberSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )


class CompanyMemberDetailView(CompanyMembersBaseView):
    """
    Cambia el rol o desvincula un usuario de una Company.

    @version 1.0
    @author Agustin
    """

    def patch(self, request, id, user_id):
        """
        Cambia el rol de un miembro sin dejar la Company sin owner.

        @version 1.0
        @author Agustin
        """
        with transaction.atomic():
            company = self.get_company(id, lock=True)
            self.require_owner(company)
            if request.user.id == user_id:
                raise PermissionDenied()

            serializer = CompanyMemberRoleSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            membership = CompanyMember.objects.filter(
                company=company,
                user_id=user_id,
            ).select_related("user", "role").first()
            if membership is None:
                raise NotFound(
                    {"code": "NEX-COM-004", "message": "Compañía no encontrada."}
                )

            role = serializer.validated_data["role"]
            if membership.role_id != role.id:
                if membership.role.code == "owner" and role.code != "owner":
                    owners = CompanyMember.objects.filter(
                        company=company,
                        role__code="owner",
                    ).count()
                    if owners == 1:
                        raise serializers.ValidationError(
                            {"role": "La compañía debe conservar al menos un owner."}
                        )
                membership.role = role
                membership.save(update_fields=["role"])

        return Response(CompanyMemberSerializer(membership).data)

    def delete(self, request, id, user_id):
        """
        Desvincula un miembro sin eliminar su usuario ni otros accesos.

        @version 1.0
        @author Agustin
        """
        with transaction.atomic():
            company = self.get_company(id, lock=True)
            self.require_owner(company)
            membership = CompanyMember.objects.filter(
                company=company,
                user_id=user_id,
            ).select_related("role").first()
            if membership is None:
                raise NotFound(
                    {"code": "NEX-COM-004", "message": "Compañía no encontrada."}
                )
            if membership.role.code == "owner":
                owners = CompanyMember.objects.filter(
                    company=company,
                    role__code="owner",
                ).count()
                if owners == 1:
                    raise serializers.ValidationError(
                        {"user_id": "La compañía debe conservar al menos un owner."}
                    )
            membership.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
