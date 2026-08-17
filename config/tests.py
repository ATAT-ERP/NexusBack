"""Tests for technical project-level behavior."""

from django.test import SimpleTestCase


class HealthCheckTests(SimpleTestCase):
    def test_health_check_reports_process_availability(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})
