import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounting.enums import AccountType, Currency, EntryOrigin, EntryStatus
from apps.accounting.models import Account, JournalEntry, JournalLine
from apps.company.models import Company


class JournalEntryTests(TestCase):
    """Verifica la creación y numeración de asientos contables.

    @version 1.0
    @author Agustin
    """

    def setUp(self):
        """Prepara dos compañías para verificar numeración independiente.

        @version 1.0
        @author Agustin
        """
        self.company = Company.objects.create(name="Primera")
        self.other_company = Company.objects.create(name="Segunda")

    def create_entry(self, company=None, **kwargs):
        """Crea un asiento para la compañía elegida.

        @version 1.0
        @author Agustin
        """
        return JournalEntry.objects.create(
            company=company or self.company,
            accounting_date=date(2026, 10, 5),
            description="Asiento de prueba",
            **kwargs,
        )

    def test_defaults_and_optional_source_id(self):
        """Aplica el estado y moneda iniciales y permite origen sin ID.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry()

        self.assertEqual(entry.status, EntryStatus.DRAFT)
        self.assertEqual(entry.currency, Currency.ARS)
        self.assertIsNone(entry.source_id)

    def test_source_id_accepts_generic_text(self):
        """Conserva identificadores externos como texto genérico.

        @version 1.0
        @author Agustin
        """
        source_id = str(uuid.uuid4())
        entry = self.create_entry(
            source_type=EntryOrigin.IMPORT,
            source_id=source_id,
        )

        self.assertEqual(entry.source_id, source_id)

    def test_numbers_are_sequential_per_company(self):
        """Numera correlativamente y reinicia la secuencia por compañía.

        @version 1.0
        @author Agustin
        """
        entries = [self.create_entry() for _ in range(3)]
        other_entry = self.create_entry(company=self.other_company)

        self.assertEqual([entry.number for entry in entries], [1, 2, 3])
        self.assertEqual(other_entry.number, 1)

    def test_save_preserves_number_and_company(self):
        """
        Rechaza cambiar la identidad numerada de un asiento existente.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry()
        for field, value in (
            ("number", 99),
            ("company", self.other_company),
            ("company_id", self.other_company.pk),
        ):
            with self.subTest(field=field):
                setattr(entry, field, value)
                with self.assertRaises(ValidationError):
                    entry.save()
                entry.refresh_from_db()
                self.assertEqual(entry.number, 1)
                self.assertEqual(entry.company_id, self.company.pk)

    def test_new_instance_cannot_overwrite_an_existing_entry(self):
        """
        Impide que una instancia nueva con ID existente renumere el asiento.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry()
        replacement = JournalEntry(
            pk=entry.pk,
            company=self.other_company,
            accounting_date=entry.accounting_date,
            description="Reemplazo",
        )
        with self.assertRaises(IntegrityError):
            replacement.save()
        entry.refresh_from_db()
        self.assertEqual(entry.number, 1)
        self.assertEqual(entry.company_id, self.company.pk)
        self.assertEqual(entry.description, "Asiento de prueba")

    def test_queryset_update_preserves_number_and_company(self):
        """
        Impide renumerar o trasladar borradores mediante update().

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry()
        for field, value in (
            ("number", 99),
            ("company", self.other_company),
            ("company_id", self.other_company.pk),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    JournalEntry.objects.filter(pk=entry.pk).update(**{field: value})
                entry.refresh_from_db()
                self.assertEqual(entry.number, 1)
                self.assertEqual(entry.company_id, self.company.pk)

    def test_bulk_update_preserves_number_and_company(self):
        """
        Comprueba que bulk_update respete la protección del QuerySet.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry()
        for field, value in (
            ("number", 99),
            ("company", self.other_company),
            ("company_id", self.other_company.pk),
        ):
            with self.subTest(field=field):
                setattr(entry, field, value)
                with self.assertRaises(ValidationError):
                    with transaction.atomic():
                        JournalEntry.objects.bulk_update([entry], [field])
                entry.refresh_from_db()
                self.assertEqual(entry.number, 1)
                self.assertEqual(entry.company_id, self.company.pk)

    def test_draft_remains_editable_through_normal_orm_operations(self):
        """
        Conserva la edición de los campos permitidos del borrador.

        @version 1.0
        @author Agustin
        """
        entry = self.create_entry()
        entry.description = "Edición individual"
        entry.save()
        JournalEntry.objects.filter(pk=entry.pk).update(description="Edición del QuerySet")
        entry.refresh_from_db()
        self.assertEqual(entry.description, "Edición del QuerySet")
        entry.description = "Edición por lote"
        JournalEntry.objects.bulk_update([entry], ["description"])
        entry.refresh_from_db()
        self.assertEqual(entry.description, "Edición por lote")


class JournalLineTests(TestCase):
    """Verifica importes y referencias de los movimientos contables.

    @version 1.0
    @author Agustin
    """

    def setUp(self):
        """Prepara asientos y cuentas de dos compañías.

        @version 1.0
        @author Agustin
        """
        self.company = Company.objects.create(name="Primera")
        self.other_company = Company.objects.create(name="Segunda")
        self.entry = self.create_entry(self.company)
        self.account = self.create_account(self.company, "1.1.01")
        self.other_account = self.create_account(self.other_company, "1.1.01")

    def create_entry(self, company):
        """Crea un asiento borrador para la compañía indicada.

        @version 1.0
        @author Agustin
        """
        return JournalEntry.objects.create(
            company=company,
            accounting_date=date(2026, 10, 5),
            description="Asiento de prueba",
        )

    def create_account(self, company, code, is_active=True):
        """Crea una cuenta de activo para las pruebas.

        @version 1.0
        @author Agustin
        """
        return Account.objects.create(
            company=company,
            code=code,
            name="Caja",
            account_type=AccountType.ASSET,
            is_active=is_active,
        )

    def make_line(self, debit, credit, account=None):
        """Construye una línea sin persistirla.

        @version 1.0
        @author Agustin
        """
        return JournalLine(
            journal_entry=self.entry,
            account=account or self.account,
            description="Movimiento de prueba",
            debit=debit,
            credit=credit,
        )

    def test_valid_debit_line(self):
        """Acepta y persiste una línea con importe en Debe.

        @version 1.0
        @author Agustin
        """
        line = self.make_line(Decimal("10.00"), Decimal("0.00"))

        line.save()

        self.assertIsNotNone(line.pk)

    def test_valid_credit_line(self):
        """Acepta y persiste una línea con importe en Haber.

        @version 1.0
        @author Agustin
        """
        line = self.make_line(Decimal("0.00"), Decimal("10.00"))

        line.save()

        self.assertIsNotNone(line.pk)

    def test_rejects_invalid_amount_combinations(self):
        """Rechaza importes positivos simultáneos, cero y negativos.

        @version 1.0
        @author Agustin
        """
        invalid_amounts = (
            (Decimal("1.00"), Decimal("1.00")),
            (Decimal("0.00"), Decimal("0.00")),
            (Decimal("-1.00"), Decimal("0.00")),
            (Decimal("0.00"), Decimal("-1.00")),
        )
        for debit, credit in invalid_amounts:
            with self.subTest(debit=debit, credit=credit):
                with self.assertRaises(ValidationError):
                    self.make_line(debit, credit).save()

    def test_database_constraint_rejects_invalid_amounts_without_model_save(self):
        """Comprueba que el CheckConstraint rechace una escritura directa.

        @version 1.0
        @author Agustin
        """
        line = self.make_line(Decimal("10.00"), Decimal("0.00"))
        line.save()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                JournalLine.objects.filter(pk=line.pk).update(
                    debit=Decimal("10.00"),
                    credit=Decimal("10.00"),
                )

    def test_rejects_account_from_another_company(self):
        """Rechaza una cuenta cuya compañía no coincide con el asiento.

        @version 1.0
        @author Agustin
        """
        with self.assertRaises(ValidationError):
            self.make_line(
                Decimal("10.00"),
                Decimal("0.00"),
                account=self.other_account,
            ).save()

    def test_rejects_inactive_account(self):
        """Rechaza una cuenta inactiva al guardar el movimiento.

        @version 1.0
        @author Agustin
        """
        inactive_account = self.create_account(
            self.company,
            "1.1.02",
            is_active=False,
        )

        with self.assertRaises(ValidationError):
            self.make_line(
                Decimal("10.00"),
                Decimal("0.00"),
                account=inactive_account,
            ).save()
