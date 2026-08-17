"""Global URL configuration and API route aggregator."""

from django.urls import include, path

from config.health import HealthCheckView


urlpatterns = [
    path("api/health/", HealthCheckView.as_view(), name="health-check"),
    path("api/", include("apps.users.api.urls")),
]
