from django.urls import include, path


urlpatterns = [
    path("cloud/", include("apps.cloud.files.api.urls")),
]
