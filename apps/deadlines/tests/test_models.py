import uuid
from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from apps.company.models import Company
from apps.deadlines.models import Deadline
from apps.users.models import User


class DeadlineModelTests(TestCase):
    def setUp(self):
        """Crea el propietario y el cliente para las pruebas. @version 1.0"""
        self.owner = User.objects.create(id=uuid.uuid4())
        self.company = Company.objects.create(name="Cliente")

    def test_create_for_individual_and_organization(self):
        """Persiste tareas para ambos tipos de cliente. @version 1.0"""
        organization = Company.objects.create(name="Empresa", type=Company.Type.ORGANIZATION)
        for company in (self.company, organization):
            deadline = Deadline.objects.create(
                owner=self.owner, company=company, name="Declaración", due_date=date(2026, 11, 1)
            )
            deadline.refresh_from_db()
            self.assertIsInstance(deadline.pk, uuid.UUID)
            self.assertEqual(deadline.status, Deadline.Status.PENDING)
            self.assertIsNone(deadline.period)
            self.assertIsNone(deadline.notes)
            self.assertIsNotNone(deadline.created_at)
            self.assertIsNotNone(deadline.updated_at)

    def test_required_fields_are_validated(self):
        """Exige propietario, compañía, nombre y vencimiento. @version 1.0"""
        with self.assertRaises(ValidationError) as error:
            Deadline().full_clean()
        self.assertTrue({"owner", "company", "name", "due_date"} <= error.exception.message_dict.keys())

    def test_status_values_are_constrained(self):
        """Acepta el estado completado y rechaza otros valores en la base. @version 1.0"""
        deadline = Deadline.objects.create(
            owner=self.owner, company=self.company, name="Tarea",
            due_date=date(2026, 11, 1), status=Deadline.Status.COMPLETED,
        )
        self.assertEqual(deadline.status, "completed")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Deadline.objects.filter(pk=deadline.pk).update(status="overdue")

    def test_company_deletion_is_protected(self):
        """Impide eliminar físicamente un cliente con tareas. @version 1.0"""
        Deadline.objects.create(
            owner=self.owner, company=self.company, name="Tarea", due_date=date(2026, 11, 1)
        )
        with self.assertRaises(ProtectedError):
            self.company.delete()

    def test_update_preserves_created_at_and_refreshes_updated_at(self):
        """Actualiza la fecha de modificación al guardar. @version 1.0"""
        deadline = Deadline.objects.create(
            owner=self.owner, company=self.company, name="Tarea", due_date=date(2026, 11, 1)
        )
        created_at, updated_at = deadline.created_at, deadline.updated_at
        deadline.name = "Tarea actualizada"
        deadline.save()
        deadline.refresh_from_db()
        self.assertEqual(deadline.created_at, created_at)
        self.assertGreater(deadline.updated_at, updated_at)

    def test_owner_deletion_cascades_to_deadlines(self):
        """Elimina las tareas junto con su propietario. @version 1.0"""
        deadline = Deadline.objects.create(
            owner=self.owner, company=self.company, name="Tarea", due_date=date(2026, 11, 1),
            period="2026-11", notes="Observación",
        )
        deadline.refresh_from_db()
        self.assertEqual(deadline.owner, self.owner)
        self.assertEqual(deadline.company, self.company)
        self.assertEqual(deadline.period, "2026-11")
        self.assertEqual(deadline.notes, "Observación")
        self.owner.delete()
        self.assertFalse(Deadline.objects.filter(pk=deadline.pk).exists())
        self.assertTrue(Company.objects.filter(pk=self.company.pk).exists())
