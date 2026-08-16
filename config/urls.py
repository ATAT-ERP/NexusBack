"""Global URL configuration and API route aggregator."""

from django.urls import path

from config.health import HealthCheckView


urlpatterns = [
    path("api/health/", HealthCheckView.as_view(), name="health-check"),
]
