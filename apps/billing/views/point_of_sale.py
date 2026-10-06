from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.models import FiscalProfile, PointOfSale
from apps.billing.serializers import PointOfSaleSerializer
from apps.billing.services.numbering import assign_point_of_sale_number
from apps.company.models import CompanyMember
from apps.users.authentication import SupabaseBearerAuthentication


class CompanyScopedBillingView:
    """
    Resuelve el FiscalProfile de la Company solicitada verificando que
    el usuario autenticado sea miembro, reutilizando la misma
    validación de acceso que FiscalProfileView.
    @version 1.0
    @author Thiago
    """

    authentication_classes = (SupabaseBearerAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_fiscal_profile(self):
        membership = (
            CompanyMember.objects.select_related("company")
            .filter(user=self.request.user, company_id=self.kwargs["company_id"])
            .first()
        )
        if membership is None:
            raise PermissionDenied()
        return get_object_or_404(FiscalProfile, company=membership.company)


class PointOfSaleListCreateView(CompanyScopedBillingView, generics.GenericAPIView):
    """
    Lista los puntos de venta de la Company autorizada y crea uno
    nuevo asignando automáticamente su número.
    @version 1.0
    @author Thiago
    """

    serializer_class = PointOfSaleSerializer

    def get(self, request, *args, **kwargs):
        fiscal_profile = self.get_fiscal_profile()
        points_of_sale = PointOfSale.objects.filter(fiscal_profile=fiscal_profile)
        return Response(self.get_serializer(points_of_sale, many=True).data)

    def post(self, request, *args, **kwargs):
        fiscal_profile = self.get_fiscal_profile()
        point_of_sale = assign_point_of_sale_number(fiscal_profile)
        return Response(
            self.get_serializer(point_of_sale).data,
            status=status.HTTP_201_CREATED,
        )


class PointOfSaleDetailView(CompanyScopedBillingView, generics.GenericAPIView):
    """
    Consulta un punto de venta puntual de la Company autorizada.
    @version 1.0
    @author Thiago
    """

    serializer_class = PointOfSaleSerializer

    def get_object(self):
        fiscal_profile = self.get_fiscal_profile()
        return get_object_or_404(
            PointOfSale, fiscal_profile=fiscal_profile, pk=self.kwargs["pk"]
        )

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_object()).data)


class PointOfSaleActivateView(CompanyScopedBillingView, APIView):
    """
    Activa un punto de venta de la Company autorizada.
    @version 1.0
    @author Thiago
    """

    def post(self, request, *args, **kwargs):
        fiscal_profile = self.get_fiscal_profile()
        point_of_sale = get_object_or_404(
            PointOfSale, fiscal_profile=fiscal_profile, pk=self.kwargs["pk"]
        )
        point_of_sale.is_active = True
        point_of_sale.save(update_fields=["is_active"])
        return Response(PointOfSaleSerializer(point_of_sale).data)


class PointOfSaleDeactivateView(CompanyScopedBillingView, APIView):
    """
    Desactiva un punto de venta de la Company autorizada.
    @version 1.0
    @author Thiago
    """

    def post(self, request, *args, **kwargs):
        fiscal_profile = self.get_fiscal_profile()
        point_of_sale = get_object_or_404(
            PointOfSale, fiscal_profile=fiscal_profile, pk=self.kwargs["pk"]
        )
        point_of_sale.is_active = False
        point_of_sale.save(update_fields=["is_active"])
        return Response(PointOfSaleSerializer(point_of_sale).data)