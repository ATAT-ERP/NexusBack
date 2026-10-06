from django.urls import path

from apps.billing.views import (
    FiscalProfileView,
    PointOfSaleActivateView,
    PointOfSaleDeactivateView,
    PointOfSaleDetailView,
    PointOfSaleListCreateView,
)


urlpatterns = [
    path(
        "companies/<uuid:company_id>/fiscal-profile/",
        FiscalProfileView.as_view(),
        name="company-fiscal-profile",
    ),
    path(
        "companies/<uuid:company_id>/points-of-sale/",
        PointOfSaleListCreateView.as_view(),
        name="company-points-of-sale",
    ),
    path(
        "companies/<uuid:company_id>/points-of-sale/<int:pk>/",
        PointOfSaleDetailView.as_view(),
        name="company-point-of-sale-detail",
    ),
    path(
        "companies/<uuid:company_id>/points-of-sale/<int:pk>/activate/",
        PointOfSaleActivateView.as_view(),
        name="company-point-of-sale-activate",
    ),
    path(
        "companies/<uuid:company_id>/points-of-sale/<int:pk>/deactivate/",
        PointOfSaleDeactivateView.as_view(),
        name="company-point-of-sale-deactivate",
    ),
]