from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.billing.models import FiscalProfile
from apps.billing.serializers import FiscalProfileSerializer
from apps.billing.views.point_of_sale import CompanyScopedBillingView
from apps.users.authentication import SupabaseBearerAuthentication


class FiscalProfileView(CompanyScopedBillingView, generics.GenericAPIView):
    """
    Consulta, crea y actualiza el perfil fiscal de una Company autorizada.
    @version 1.0
    @author Agustin
    """

    serializer_class = FiscalProfileSerializer
    authentication_classes = (SupabaseBearerAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        """
        Devuelve el perfil fiscal de la Company autorizada.
        @version 1.0
        @author Agustin
        """
        company = self.get_company()
        profile = get_object_or_404(FiscalProfile, company=company)
        return Response(self.get_serializer(profile).data)

    def post(self, request, *args, **kwargs):
        """
        Crea el perfil fiscal asociado a la Company autorizada.
        @version 1.0
        @author Agustin
        """
        company = self.get_company()
        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), "company": company},
        )
        serializer.is_valid(raise_exception=True)
        profile = serializer.save(company=company)
        return Response(
            self.get_serializer(profile).data,
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, *args, **kwargs):
        """
        Reemplaza los campos editables del perfil fiscal existente.
        @version 1.0
        @author Agustin
        """
        return self._update(request, partial=False)

    def patch(self, request, *args, **kwargs):
        """
        Actualiza parcialmente el perfil fiscal existente.
        @version 1.0
        @author Agustin
        """
        return self._update(request, partial=True)

    def _update(self, request, partial):
        """
        Guarda cambios validados en el perfil fiscal de la Company autorizada.
        @version 1.0
        @author Agustin
        """
        company = self.get_company()
        profile = get_object_or_404(FiscalProfile, company=company)
        serializer = self.get_serializer(profile, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)