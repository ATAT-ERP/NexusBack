import uuid
from datetime import date, datetime, timezone
from unittest.mock import patch

from rest_framework.test import APITestCase

from apps.company.models import Company, CompanyMember, CompanyRole
from apps.deadlines.models import Deadline
from apps.users.models import User


class DeadlineQueryTests(APITestCase):
    url = "/api/deadlines/"

    def setUp(self):
        """Prepara tareas de distintos propietarios y compañías. @version 1.0"""
        self.user = User.objects.create(id=uuid.uuid4())
        other = User.objects.create(id=uuid.uuid4())
        self.first = Company.objects.create(name="Uno")
        self.second = Company.objects.create(name="Dos")
        self.revoked = Company.objects.create(name="Revocada")
        self.foreign = Company.objects.create(name="Ajena")
        role = CompanyRole.objects.get(code="member")
        for user, company in ((self.user, self.first), (self.user, self.second),
                              (other, self.first), (other, self.foreign)):
            CompanyMember.objects.create(user=user, company=company, role=role)
        self.early = Deadline.objects.create(
            owner=self.user, company=self.first, name="Anterior", due_date=date(2026, 1, 1)
        )
        self.middle = Deadline.objects.create(
            owner=self.user, company=self.second, name="Media", due_date=date(2026, 1, 2)
        )
        self.completed = Deadline.objects.create(
            owner=self.user, company=self.second, name="Terminada", due_date=date(2026, 1, 2),
            status=Deadline.Status.COMPLETED,
        )
        Deadline.objects.create(owner=other, company=self.first, name="Ajena", due_date=date(2026, 1, 2))
        Deadline.objects.create(owner=other, company=self.foreign, name="Ajena 2", due_date=date(2026, 1, 2))
        Deadline.objects.create(owner=self.user, company=self.revoked, name="Revocada", due_date=date(2026, 1, 2))
        self.client.force_authenticate(self.user)

    def test_individual_filters_and_stable_order(self):
        """Filtra por cada parámetro y ordena por fecha y UUID. @version 1.0"""
        same_day = sorted([str(self.middle.id), str(self.completed.id)])
        cases = (
            ({}, [str(self.early.id)] + same_day),
            ({"company_id": str(self.first.id)}, [str(self.early.id)]),
            ({"status": "completed"}, [str(self.completed.id)]),
            ({"due_date_from": "2026-01-02"}, same_day),
            ({"due_date_to": "2026-01-01"}, [str(self.early.id)]),
        )
        for params, expected in cases:
            with self.subTest(params=params):
                response = self.client.get(self.url, params)
                self.assertEqual(response.status_code, 200)
                self.assertEqual([item["id"] for item in response.data], expected)

    def test_combined_filters_preserve_access_control(self):
        """Combina límites inclusivos sin exponer tareas ajenas o revocadas. @version 1.0"""
        params = {"company_id": str(self.second.id), "status": "pending",
                  "due_date_from": "2026-01-02", "due_date_to": "2026-01-02"}
        response = self.client.get(self.url, params)
        self.assertEqual([item["id"] for item in response.data], [str(self.middle.id)])
        for company in (self.foreign, self.revoked):
            params["company_id"] = str(company.id)
            response = self.client.get(self.url, params)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, [])
        response = self.client.get(self.url, {"company_id": str(self.first.id)})
        self.assertEqual([item["id"] for item in response.data], [str(self.early.id)])

    def test_invalid_filters_are_rejected(self):
        """Rechaza UUID, estados, fechas y rangos inválidos. @version 1.0"""
        cases = (
            {"company_id": "incorrecto"}, {"status": "overdue"}, {"status": ""},
            {"due_date_from": "hoy"}, {"due_date_to": "2026-02-30"},
            {"due_date_from": "2026-01-03", "due_date_to": "2026-01-02"},
        )
        for params in cases:
            with self.subTest(params=params):
                self.assertEqual(self.client.get(self.url, params).status_code, 400)

    @patch("django.utils.timezone.now", return_value=datetime(2026, 1, 2, 1, 0, tzinfo=timezone.utc))
    def test_indicators_use_argentina_date_and_pending_status(self, mock_now):
        """Comprueba límites y completadas cuando UTC ya cambió de día. @version 1.0"""
        deadlines = {}
        for label, day, state in (
            ("ayer", 31, "pending"), ("hoy", 1, "pending"),
            ("siete", 8, "pending"), ("ocho", 9, "pending"),
            ("completada_atrasada", 31, "completed"),
            ("completada_proxima", 1, "completed"),
        ):
            due = date(2025, 12, day) if day == 31 else date(2026, 1, day)
            deadlines[label] = Deadline.objects.create(
                owner=self.user, company=self.first, name=label, due_date=due, status=state
            )
        response = self.client.get(self.url)
        items = {item["id"]: item for item in response.data}
        for label, expected in (("ayer", (True, False)), ("hoy", (False, True)),
                                ("siete", (False, True)), ("ocho", (False, False)),
                                ("completada_atrasada", (False, False)),
                                ("completada_proxima", (False, False))):
            with self.subTest(label=label):
                item = items[str(deadlines[label].id)]
                self.assertEqual((item["overdue"], item["due_soon"]), expected)
        detail = self.client.get(f"{self.url}{deadlines['hoy'].id}/")
        self.assertEqual((detail.data["overdue"], detail.data["due_soon"]), (False, True))
        changed = self.client.patch(f"{self.url}{deadlines['hoy'].id}/", {
            "overdue": True, "due_soon": False, "status": "completed"
        }, format="json")
        self.assertEqual((changed.data["overdue"], changed.data["due_soon"]), (False, False))
