from django.urls import path

from apps.billing.views import (
    FiscalProfileView,
    InvoiceDetailView,
    InvoiceIssueView,
    InvoiceItemDetailView,
    InvoiceItemListCreateView,
    InvoiceListCreateView,
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
    path(
        "companies/<uuid:company_id>/invoices/",
        InvoiceListCreateView.as_view(),
        name="company-invoices",
    ),
    path(
        "companies/<uuid:company_id>/invoices/<int:pk>/",
        InvoiceDetailView.as_view(),
        name="company-invoice-detail",
    ),
    path(
        "companies/<uuid:company_id>/invoices/<int:pk>/issue/",
        InvoiceIssueView.as_view(),
        name="company-invoice-issue",
    ),
    path(
        "companies/<uuid:company_id>/invoices/<int:invoice_id>/items/",
        InvoiceItemListCreateView.as_view(),
        name="company-invoice-items",
    ),
    path(
        "companies/<uuid:company_id>/invoices/<int:invoice_id>/items/<int:pk>/",
        InvoiceItemDetailView.as_view(),
        name="company-invoice-item-detail",
    ),
]
