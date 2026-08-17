from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.users.api.views import LoginView, LogoutView, RegisterView, UserViewSet


router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("users/register/", RegisterView.as_view(), name="user-register"),
    path("users/login/", LoginView.as_view(), name="user-login"),
    path("users/logout/", LogoutView.as_view(), name="user-logout"),
] + router.urls
