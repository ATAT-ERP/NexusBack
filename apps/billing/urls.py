from django.urls import path

from apps.billing.views import FiscalProfileView


urlpatterns = [
    path(
        "companies/<uuid:company_id>/fiscal-profile/",
        FiscalProfileView.as_view(),
        name="company-fiscal-profile",
    ),
]
