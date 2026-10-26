import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import DatabaseError, close_old_connections, connections
from django.test import TransactionTestCase, override_settings
from reportlab.platypus.doctemplate import LayoutError
from rest_framework.test import APIClient
from storage3.exceptions import StorageApiError

from apps.billing.enums.invoice import CreditNoteType, InvoiceStatus
from apps.billing.models import CreditNote, CreditNoteInvoice, CreditNoteItem, FiscalProfile, Invoice, InvoiceSequence
from apps.billing.services.issuing import issue_credit_note, issue_invoice
from apps.billing.services.representation import get_representation
from apps.billing.tests.test_credit_note import create_invoice
from apps.billing.tests.test_invoice_issue import InvoiceFlowTestCase
from apps.cloud.models import File
from apps.company.models import Company, CompanyMember, CompanyRole
from apps.users.models import User


class InvoiceRepresentationTests(InvoiceFlowTestCase):
    def representation_url(self, document):
        """Devuelve la ruta de representación del documento. @version 1.0"""
        resource = "credit-notes" if isinstance(document, CreditNote) else "invoices"
        return f"/api/billing/companies/{self.company.id}/{resource}/{document.pk}/representation/"

    @patch("apps.cloud.files.services.storage_client")
    def test_stores_and_reuses_issued_invoice(self, storage):
        """Asocia un único PDF, consulta sin generar y reutiliza en POST. @version 1.0"""
        invoice = issue_invoice(self.make_invoice())
        url = self.representation_url(invoice)
        self.assertEqual(self.client.get(url).status_code, 404)
        storage.storage.from_.assert_not_called()

        response = self.client.post(url)

        self.assertEqual(response.status_code, 201)
        invoice.refresh_from_db()
        file = invoice.representation_file
        self.assertEqual(file.company, self.company)
        self.assertEqual(file.mime_type, "application/pdf")
        self.assertEqual(str(file.pk), response.data["file"]["id"])
        self.assertNotIn("storage_key", response.data["file"])
        self.assertEqual(response.data["download_url"], f"/api/cloud/files/{file.pk}/download/")
        content = storage.storage.from_().upload.call_args.args[1]
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertEqual(file.size, len(content))
        self.assertEqual(file.original_name, "invoice-00001-00000001.pdf")
        self.assertEqual(self.client.get(url).data, response.data)
        reused = self.client.post(url)
        self.assertEqual(reused.status_code, 200)
        self.assertEqual(reused.data, response.data)
        self.assertEqual(File.objects.count(), 1)
        storage.storage.from_().upload.assert_called_once()

    @patch("apps.cloud.files.services.storage_client")
    def test_draft_is_rejected_for_generation_and_lookup(self, storage):
        """No genera ni almacena representaciones de borradores. @version 1.0"""
        invoice = self.make_invoice()
        for method in (self.client.post, self.client.get):
            response = method(self.representation_url(invoice))
            self.assertEqual(response.status_code, 400)
            self.assertIn("status", response.data)
        self.assertFalse(File.objects.exists())
        storage.storage.from_.assert_not_called()

    @patch("apps.cloud.files.services.storage_client")
    def test_storage_failure_keeps_issuance_and_allows_retry(self, storage):
        """Fallar en Cloud no altera emisión, snapshot ni correlativo. @version 1.0"""
        invoice = issue_invoice(self.make_invoice())
        number = invoice.number
        sequence = InvoiceSequence.objects.get().last_number
        storage.storage.from_().upload.side_effect = StorageApiError("Unavailable", "InternalError", 500)

        response = self.client.post(self.representation_url(invoice))

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["code"], "NEX-DOC-003")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertEqual(invoice.number, number)
        self.assertEqual(invoice.issuer_legal_name, "Emisor S.A.")
        self.assertEqual(InvoiceSequence.objects.get().last_number, sequence)
        self.assertIsNone(invoice.representation_file_id)
        self.assertFalse(File.objects.exists())
        storage.storage.from_().upload.side_effect = None
        self.assertEqual(self.client.post(self.representation_url(invoice)).status_code, 201)

    @patch("apps.cloud.files.services.storage_client")
    @patch("apps.billing.services.representation.render_pdf", side_effect=LayoutError("layout"))
    def test_generation_failure_keeps_issuance(self, render, storage):
        """Un error de PDF no modifica el comprobante emitido. @version 1.0"""
        invoice = issue_invoice(self.make_invoice())
        response = self.client.post(self.representation_url(invoice))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["code"], "NEX-BIL-001")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertEqual(invoice.number, 1)
        self.assertIsNone(invoice.representation_file_id)
        self.assertFalse(File.objects.exists())
        storage.storage.from_.assert_not_called()

    @patch("apps.cloud.files.services.storage_client")
    def test_association_failure_cleans_upload_and_rolls_back_file(self, storage):
        """Cloud limpia la carga si falla la asociación en Billing. @version 1.0"""
        invoice = issue_invoice(self.make_invoice())
        with patch.object(Invoice, "save", side_effect=DatabaseError("association")):
            response = self.client.post(self.representation_url(invoice))
        self.assertEqual(response.status_code, 500)
        storage_key = storage.storage.from_().upload.call_args.args[0]
        storage.storage.from_().remove.assert_called_once_with([storage_key])
        self.assertFalse(File.objects.exists())
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertIsNone(invoice.representation_file_id)

    @override_settings(DOCUMENT_MAX_SIZE_BYTES=1)
    @patch("apps.cloud.files.services.storage_client")
    def test_applies_cloud_file_size_limit(self, storage):
        """La generación respeta los límites de archivo de Cloud. @version 1.0"""
        invoice = issue_invoice(self.make_invoice())
        response = self.client.post(self.representation_url(invoice))
        self.assertEqual(response.status_code, 400)
        self.assertIn("file", response.data)
        self.assertFalse(File.objects.exists())
        storage.storage.from_.assert_not_called()

    @patch("apps.cloud.files.services.storage_client")
    def test_inactive_company_reuses_existing_but_cannot_generate(self, storage):
        """Permite lectura histórica y reutilización, pero no nuevas cargas. @version 1.0"""
        first = issue_invoice(self.make_invoice())
        second = issue_invoice(self.make_invoice())
        existing = self.client.post(self.representation_url(first)).data
        self.company.is_active = False
        self.company.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(self.representation_url(first)).data, existing)
        self.assertEqual(self.client.post(self.representation_url(first)).data, existing)
        self.assertEqual(self.client.post(self.representation_url(second)).status_code, 403)
        storage.storage.from_().upload.assert_called_once()

    @patch("apps.cloud.files.services.storage_client")
    def test_company_and_membership_are_required(self, storage):
        """No admite acceso por otra Company ni sin membresía. @version 1.0"""
        invoice = issue_invoice(self.make_invoice())
        other = Company.objects.create(name="Otra Company")
        CompanyMember.objects.create(
            company=other, user=self.user, role=CompanyRole.objects.get(code="member")
        )
        wrong_url = self.representation_url(invoice).replace(str(self.company.pk), str(other.pk))
        for method in (self.client.get, self.client.post):
            self.assertEqual(method(wrong_url).status_code, 404)
        outsider = User.objects.create(id=uuid.uuid4(), email="representation-outsider@example.com")
        self.client.force_authenticate(user=outsider)
        for method in (self.client.get, self.client.post):
            self.assertEqual(method(self.representation_url(invoice)).status_code, 403)
        self.assertEqual(APIClient().post(self.representation_url(invoice)).status_code, 401)
        storage.storage.from_.assert_not_called()

    @patch("apps.cloud.files.api.views.storage_client")
    @patch("apps.cloud.files.services.storage_client")
    def test_download_uses_cloud_and_rechecks_membership(self, upload_storage, download_storage):
        """La ruta retornada usa signed URL y exige membresía vigente. @version 1.0"""
        invoice = issue_invoice(self.make_invoice())
        response = self.client.post(self.representation_url(invoice))
        url = response.data["download_url"]
        invoice.refresh_from_db()
        file = invoice.representation_file
        download_storage.storage.from_().create_signed_url.return_value = {"signedURL": "https://example.test/signed"}
        self.assertEqual(self.client.get(url).data, {"url": "https://example.test/signed"})
        download_storage.storage.from_().create_signed_url.assert_called_once_with(
            file.storage_key, 60, {"download": file.original_name}
        )
        CompanyMember.objects.filter(company=self.company, user=self.user).delete()
        self.assertEqual(self.client.get(url).status_code, 404)
        download_storage.storage.from_().create_signed_url.assert_called_once()

    @patch("apps.cloud.files.services.storage_client")
    def test_issuance_does_not_call_cloud(self, storage):
        """Emitir no requiere generar ni almacenar un PDF. @version 1.0"""
        invoice = self.make_invoice()
        self.assertEqual(self.client.post(self.issue_url(invoice)).status_code, 200)
        invoice.refresh_from_db()
        self.assertIsNone(invoice.representation_file_id)
        storage.storage.from_.assert_not_called()

    @patch("apps.cloud.files.services.storage_client")
    def test_credit_note_and_cancelled_invoice_representations(self, storage):
        """Representa NC emitidas y facturas totalmente acreditadas. @version 1.0"""
        invoice = issue_invoice(self.make_invoice())
        credit_note = CreditNote.objects.create(
            point_of_sale=self.point_of_sale, credit_note_type=CreditNoteType.CREDIT_NOTE_B
        )
        self.assertEqual(self.client.post(self.representation_url(credit_note)).status_code, 400)
        association = CreditNoteInvoice.objects.create(credit_note=credit_note, invoice=invoice)
        item = invoice.items.get()
        CreditNoteItem.objects.create(
            credit_note_invoice=association, description=item.description,
            quantity=item.quantity, unit_price=item.unit_price, discount=item.discount,
            tax_treatment=item.tax_treatment, vat_rate=item.vat_rate,
        )
        credit_note = issue_credit_note(credit_note)
        response = self.client.post(self.representation_url(credit_note))
        self.assertEqual(response.status_code, 201)
        credit_note.refresh_from_db()
        self.assertEqual(credit_note.representation_file.company, self.company)
        self.assertEqual(self.client.get(self.representation_url(credit_note)).data, response.data)
        self.assertEqual(self.client.post(self.representation_url(credit_note)).status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.CANCELLED)
        self.assertEqual(self.client.post(self.representation_url(invoice)).status_code, 201)
        self.assertEqual(File.objects.count(), 2)


class RepresentationConcurrencyTests(TransactionTestCase):
    @patch("apps.cloud.files.services.storage_client")
    def test_simultaneous_requests_create_one_file(self, storage):
        """Dos conexiones concurrentes reutilizan el mismo File. @version 1.0"""
        company = Company.objects.create(name="Concurrente")
        profile = FiscalProfile.objects.create(company=company, vat_condition=1)
        point_of_sale = profile.points_of_sale.create(number=1)
        user = User.objects.create(id=uuid.uuid4(), email="concurrent@example.com")
        role, _ = CompanyRole.objects.get_or_create(code="owner")
        CompanyMember.objects.create(company=company, user=user, role=role)
        invoice = create_invoice(point_of_sale, number=1)
        barrier = Barrier(2)

        def generate():
            """Ejecuta una solicitud en una conexión independiente. @version 1.0"""
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                file, created = get_representation(invoice, user)
                return file.pk, created
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(generate) for _ in range(2)]
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sorted(created for _, created in results), [False, True])
        self.assertEqual(File.objects.count(), 1)
        storage.storage.from_().upload.assert_called_once()
