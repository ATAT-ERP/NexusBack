"""Global URL configuration and API route aggregator."""

from django.contrib import admin
from django.urls import path

from config.health import HealthCheckView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthCheckView.as_view(), name="health-check"),
]
