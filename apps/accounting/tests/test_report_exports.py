import csv
import io
import uuid
from datetime import date

from rest_framework.test import APIClient

from apps.accounting.services import reverse_journal_entry
from apps.accounting.tests.test_reports import AccountingReportTestCase


class AccountingCSVTests(AccountingReportTestCase):
    """Verifica descargas CSV, equivalencia contable y acceso por Company.

    @version 1.0
    """

    def report_urls(self):
        """Enumera los tres reportes JSON y sus exportaciones correspondientes.

        @version 1.0
        """
        return (self.diary_url, self.ledger_url(self.caja), self.trial_url)

    def read_csv(self, url, params=None):
        """Comprueba la descarga y lee sus filas sin perder precisión decimal.

        @version 1.0
        """
        response = self.client.get(f"{url}export/", params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertTrue(response["Content-Disposition"].startswith('attachment; filename="'))
        self.assertTrue(response["Content-Disposition"].endswith('.csv"'))
        self.assertIn(str(self.company.pk), response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))

    def test_exports_match_json_with_filters_and_reversals(self):
        """Conserva orden, importes, reversiones, filtros y saldo previo del JSON.

        @version 1.0
        """
        reverse_journal_entry(self.entry_1.pk, user=self.user)
        filters = (
            {},
            {"accounting_date_from": "2026-02-01"},
            {"accounting_date_to": "2026-01-31"},
            {"accounting_date_from": "2026-02-01", "accounting_date_to": "2026-02-28"},
        )
        for params in filters:
            for url in self.report_urls():
                with self.subTest(url=url, params=params):
                    response = self.client.get(url, params)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response["Content-Type"], "application/json")
                    self.assertNotIn("Content-Disposition", response)
                    self.assertIsInstance(response.data, list)
                    if url == self.diary_url:
                        expected = [
                            [str(value) for value in (
                                entry["accounting_date"], entry["number"], entry["description"],
                                entry["status"], entry["currency"], line["account_code"],
                                line["account_name"], line["description"], line["debit"], line["credit"],
                            )]
                            for entry in response.data
                            for line in entry["lines"]
                        ]
                    else:
                        fields = (
                            ("code", "name", "total_debit", "total_credit", "balance")
                            if url == self.trial_url else
                            ("accounting_date", "entry_number", "description", "debit", "credit", "balance")
                        )
                        expected = [[str(row[field]) for field in fields] for row in response.data]
                    self.assertEqual(self.read_csv(url, params)[1:], expected)

    def test_headers_and_decimal_precision(self):
        """Mantiene centavos e importes grandes sin conversión a punto flotante.

        @version 1.0
        """
        self.create_published_entry(
            date(2026, 6, 1), "Ajuste de precisión", self.banco, self.otros,
            "9999999999999999.99",
        )
        cases = (
            (self.diary_url, ["Fecha contable", "Número de asiento", "Descripción del asiento", "Estado", "Moneda", "Código de cuenta", "Nombre de cuenta", "Descripción del movimiento", "Debe", "Haber"]),
            (self.ledger_url(self.banco), ["Fecha contable", "Número de asiento", "Descripción", "Debe", "Haber", "Saldo"]),
            (self.trial_url, ["Código de cuenta", "Nombre de cuenta", "Total Debe", "Total Haber", "Saldo"]),
        )
        for url, headers in cases:
            with self.subTest(url=url):
                rows = self.read_csv(url, {"accounting_date_from": "2026-06-01"})
                self.assertEqual(rows[0], headers)
                self.assertIn("9999999999999999.99", rows[1])

    def test_spanish_and_csv_special_characters(self):
        """Conserva tildes, comas, comillas y saltos de línea en los textos.

        @version 1.0
        """
        description = 'Registración, "año"\nsegunda línea'
        self.banco.name = 'Banco, "pesos" y artículos'
        self.banco.save()
        self.create_published_entry(date(2026, 6, 1), description, self.banco, self.otros, "0.01")
        params = {"accounting_date_from": "2026-06-01"}
        diary = self.read_csv(self.diary_url, params)
        self.assertEqual(diary[1][2], description)
        self.assertEqual(diary[1][6], self.banco.name)
        self.assertEqual(diary[1][7], description)
        self.assertEqual(self.read_csv(self.ledger_url(self.banco), params)[1][2], description)
        self.assertEqual(self.read_csv(self.trial_url, params)[1][1], self.banco.name)

    def test_empty_exports_keep_headers(self):
        """Descarga encabezados sin filas para cuentas o rangos sin movimientos.

        @version 1.0
        """
        for url in (*self.report_urls(), self.ledger_url(self.banco)):
            with self.subTest(url=url):
                rows = self.read_csv(url, {"accounting_date_from": "2026-03-01"})
                self.assertEqual(len(rows), 1)
                self.assertTrue(rows[0])

    def test_exports_require_authentication_and_membership(self):
        """Rechaza usuarios anónimos y consultas a Companies sin membresía.

        @version 1.0
        """
        anonymous = APIClient()
        for url in self.report_urls():
            with self.subTest(url=url):
                self.assertEqual(anonymous.get(f"{url}export/").status_code, 401)
                other_url = url.replace(str(self.company.pk), str(self.other_company.pk))
                response = self.client.get(f"{other_url}export/")
                self.assertEqual(response.status_code, 403)
                self.assertNotIn("Content-Disposition", response)

    def test_exports_preserve_validation_errors(self):
        """Devuelve los mismos errores JSON ante fechas o recursos inválidos.

        @version 1.0
        """
        for url in self.report_urls():
            for field in ("accounting_date_from", "accounting_date_to"):
                with self.subTest(url=url, field=field):
                    params = {field: "no-es-fecha"}
                    response = self.client.get(f"{url}export/", params)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.data, self.client.get(url, params).data)
                    self.assertNotIn("Content-Disposition", response)
            missing_url = url.replace(str(self.company.pk), str(uuid.uuid4()))
            self.assertEqual(self.client.get(f"{missing_url}export/").status_code, 404)
        for account_id in (self.ajena.pk, 999999):
            url = self.ledger_url(self.caja).replace(f"/{self.caja.pk}/", f"/{account_id}/")
            self.assertEqual(self.client.get(f"{url}export/").status_code, 404)

    def test_exports_exclude_drafts_and_other_companies(self):
        """Ignora borradores y movimientos ajenos dentro del rango solicitado.

        @version 1.0
        """
        params = {"accounting_date_from": "2026-03-01", "accounting_date_to": "2026-12-31"}
        for url in self.report_urls():
            with self.subTest(url=url):
                self.assertEqual(len(self.read_csv(url, params)), 1)
