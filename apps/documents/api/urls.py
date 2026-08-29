from rest_framework.routers import SimpleRouter

from apps.documents.api.views import DocumentViewSet


router = SimpleRouter()
router.register("documents", DocumentViewSet, basename="document")

urlpatterns = router.urls
