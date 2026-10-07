from rest_framework.routers import SimpleRouter

from apps.cloud.files.api.views import FileViewSet


router = SimpleRouter()
router.register("files", FileViewSet, basename="file")

urlpatterns = router.urls
