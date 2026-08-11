"""Technical endpoints maintained by the global project configuration."""

from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """Return process availability without touching the database."""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        return Response({"status": "ok"})
