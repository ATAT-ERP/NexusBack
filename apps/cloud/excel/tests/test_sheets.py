import uuid
from datetime import date, datetime, time
from io import BytesIO
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from storage3.exceptions import StorageApiError

from apps.company.models import Company, CompanyMember, CompanyRole
from apps.cloud.models import File
from apps.users.models import User


class ExcelEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(id=uuid.uuid4(), email="member@example.com")
        self.company = Company.objects.create(name="Compañía de prueba")
        self.file = self.create_file()
        CompanyMember.objects.create(
            user=self.user,
            company=self.company,
            role=CompanyRole.objects.get(code="owner"),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.sheets_url = f"/api/cloud/files/{self.file.id}/sheets/"
        self.sheet_url = f"{self.sheets_url}Clientes/"
        self.workbook = self.create_workbook()

    def create_file(self, company=None, name="clientes.xlsx"):
        return File.objects.create(
            company=company or self.company,
            name=name,
            original_name=name,
            storage_key="company/file",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            size=100,
        )

    @staticmethod
    def create_workbook():
        content = BytesIO()
        date_value = (date(2025, 4, 3) - date(1899, 12, 30)).days
        datetime_value = date_value + (12 * 60 + 30) / (24 * 60)
        time_value = (9 * 60 + 15) / (24 * 60)

        def cell(reference, value, style=None, cell_type=None):
            style_attribute = f' s="{style}"' if style is not None else ""
            type_attribute = f' t="{cell_type}"' if cell_type else ""
            cell_value = value if value.startswith("<") else f"<v>{value}</v>"
            return (
                f'<c r="{reference}"{style_attribute}{type_attribute}>'
                f"{cell_value}</c>"
            )

        def text_cell(reference, value):
            return cell(
                reference,
                f"<is><t>{escape(value)}</t></is>",
                cell_type="inlineStr",
            )

        headers = [
            "Nombre",
            "Cantidad",
            "Saldo",
            "Activo",
            "Nota",
            "Fecha",
            "Actualizado",
            "Hora",
            "Fórmula",
        ]
        columns = "ABCDEFGHI"
        header_row = "".join(
            text_cell(f"{column}1", value)
            for column, value in zip(columns, headers)
        )
        values = "".join(
            (
                text_cell("A2", "Empresa A"),
                cell("B2", "3"),
                cell("C2", "15000.5"),
                cell("D2", "1", cell_type="b"),
                cell("F2", str(date_value), style=1),
                cell("G2", str(datetime_value), style=2),
                cell("H2", str(time_value), style=3),
                cell("I2", "<f>1+1</f><v></v>"),
            )
        )
        sheet = (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData><row r=\"1\">{header_row}</row>"
            f"<row r=\"2\">{values}</row></sheetData></worksheet>"
        )
        workbook_files = {
            "[Content_Types].xml": (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                '</Types>'
            ),
            "_rels/.rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                '</Relationships>'
            ),
            "xl/workbook.xml": (
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Clientes" sheetId="1" r:id="rId1"/>'
                '<sheet name="Ventas" sheetId="2" r:id="rId2"/></sheets></workbook>'
            ),
            "xl/_rels/workbook.xml.rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
                '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                '</Relationships>'
            ),
            "xl/worksheets/sheet1.xml": sheet,
            "xl/worksheets/sheet2.xml": (
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetData/></worksheet>'
            ),
            "xl/styles.xml": (
                '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<numFmts count="3"><numFmt numFmtId="164" formatCode="yyyy-mm-dd"/>'
                '<numFmt numFmtId="165" formatCode="yyyy-mm-dd hh:mm"/>'
                '<numFmt numFmtId="166" formatCode="hh:mm"/></numFmts>'
                '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
                '<fills count="2"><fill><patternFill patternType="none"/></fill>'
                '<fill><patternFill patternType="gray125"/></fill></fills>'
                '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
                '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
                '<cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
                '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0"/>'
                '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0"/>'
                '<xf numFmtId="166" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
                '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
                '</styleSheet>'
            ),
        }
        with ZipFile(content, "w", ZIP_DEFLATED) as archive:
            for name, xml in workbook_files.items():
                archive.writestr(name, xml)
        return content.getvalue()

    @patch("apps.cloud.files.api.views.storage_client")
    def test_lists_sheets_from_a_valid_workbook(self, storage_client):
        storage_client.storage.from_().download.return_value = self.workbook

        response = self.client.get(self.sheets_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"sheets": ["Clientes", "Ventas"]})
        storage_client.storage.from_.assert_any_call("documents")
        storage_client.storage.from_().download.assert_called_once_with(
            self.file.storage_key
        )

    @patch("apps.cloud.files.api.views.storage_client")
    def test_reads_historical_workbook_from_an_inactive_company(self, storage_client):
        self.company.is_active = False
        self.company.save(update_fields=["is_active"])
        storage_client.storage.from_().download.return_value = self.workbook

        response = self.client.get(self.sheets_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"sheets": ["Clientes", "Ventas"]})
        storage_client.storage.from_().download.assert_called_once_with(
            self.file.storage_key
        )

    @patch("apps.cloud.files.api.views.storage_client")
    def test_reads_values_and_json_compatible_dates_from_a_sheet(self, storage_client):
        storage_client.storage.from_().download.return_value = self.workbook

        response = self.client.get(self.sheet_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["name"], "Clientes")
        self.assertEqual(
            data["rows"][0],
            [
                "Nombre",
                "Cantidad",
                "Saldo",
                "Activo",
                "Nota",
                "Fecha",
                "Actualizado",
                "Hora",
                "Fórmula",
            ],
        )
        row = data["rows"][1]
        self.assertEqual(row[:5], ["Empresa A", 3, 15000.5, True, None])
        self.assertEqual(row[5], "2025-04-03")
        self.assertEqual(row[6], "2025-04-03T12:30:00")
        self.assertEqual(row[7], "09:15:00")
        self.assertIsNone(row[8])

    @patch("apps.cloud.files.api.views.storage_client")
    def test_returns_not_found_for_a_missing_sheet(self, storage_client):
        storage_client.storage.from_().download.return_value = self.workbook

        response = self.client.get(f"{self.sheets_url}Inexistente/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data,
            {"code": "NEX-DOC-007", "message": "Hoja no encontrada."},
        )

    @patch("apps.cloud.files.api.views.storage_client")
    def test_rejects_files_without_xlsx_extension(self, storage_client):
        self.file.original_name = "clientes.csv"
        self.file.save(update_fields=["original_name"])

        response = self.client.get(self.sheets_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "NEX-DOC-001")
        storage_client.storage.from_.assert_not_called()

    @patch("apps.cloud.files.api.views.storage_client")
    def test_reports_an_invalid_xlsx_file(self, storage_client):
        storage_client.storage.from_().download.return_value = b"invalid xlsx"

        response = self.client.get(self.sheets_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {
                "code": "NEX-DOC-006",
                "message": "El archivo XLSX no es válido.",
            },
        )

    @patch("apps.cloud.files.api.views.storage_client")
    def test_reports_storage_errors_while_reading(self, storage_client):
        storage_client.storage.from_().download.side_effect = StorageApiError(
            "Storage unavailable",
            "InternalError",
            500,
        )

        response = self.client.get(self.sheets_url)

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(
            response.data,
            {
                "code": "NEX-DOC-005",
                "message": "No fue posible leer el archivo almacenado.",
            },
        )

    @patch("apps.cloud.files.api.views.storage_client")
    def test_returns_file_not_found_for_unknown_id(self, storage_client):
        response = self.client.get(f"/api/cloud/files/{uuid.uuid4()}/sheets/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data,
            {"code": "NEX-DOC-002", "message": "Documento no encontrado."},
        )
        storage_client.storage.from_.assert_not_called()

    @patch("apps.cloud.files.api.views.storage_client")
    def test_denies_a_user_without_membership_in_the_file_company(self, storage_client):
        other_company = Company.objects.create(name="Otra compañía")
        other_file = self.create_file(company=other_company)

        response = self.client.get(f"/api/cloud/files/{other_file.id}/sheets/")
        missing = self.client.get(f"/api/cloud/files/{uuid.uuid4()}/sheets/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data,
            {"code": "NEX-DOC-002", "message": "Documento no encontrado."},
        )
        self.assertEqual(response.data, missing.data)
        storage_client.storage.from_.assert_not_called()

    @patch("apps.cloud.files.api.views.storage_client")
    def test_sheet_values_hide_documents_without_membership(self, storage_client):
        other_company = Company.objects.create(name="Otra compañía")
        other_file = self.create_file(company=other_company)

        response = self.client.get(
            f"/api/cloud/files/{other_file.id}/sheets/Clientes/"
        )
        missing = self.client.get(
            f"/api/cloud/files/{uuid.uuid4()}/sheets/Clientes/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data,
            {"code": "NEX-DOC-002", "message": "Documento no encontrado."},
        )
        self.assertEqual(response.data, missing.data)
        storage_client.storage.from_.assert_not_called()

    def test_requires_authentication(self):
        client = APIClient()

        response = client.get(self.sheets_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
