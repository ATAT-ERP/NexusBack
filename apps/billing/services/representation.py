from io import BytesIO
from xml.sax.saxutils import escape

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer
from rest_framework.exceptions import ValidationError

from apps.billing.enums.invoice import InvoiceStatus
from apps.billing.models import CreditNote
from apps.cloud.files.services import check_company_access, cleanup_upload, create_file


def get_representation(document, user):
    """Genera una sola representación por comprobante sin intervenir en su emisión.

    El bloqueo serializa solicitudes simultáneas. Una factura cancelada por NC
    también conserva su representación histórica. Los fallos admiten reintento.
    @version 1.0
    @author Agustin
    """
    file = None
    try:
        with transaction.atomic():
            document = (
                type(document).objects.select_for_update(of=("self",))
                .select_related("point_of_sale__fiscal_profile")
                .get(pk=document.pk)
            )
            company_id = document.point_of_sale.fiscal_profile.company_id
            check_company_access(company_id, user)
            validate_representable(document)
            if document.representation_file_id:
                return document.representation_file, False
            content = render_pdf(document)
            file = create_file(
                user=user,
                data={
                    "company_id": company_id,
                    "file": SimpleUploadedFile(
                        f"{document._meta.model_name}-{document.point_of_sale.formatted_number}-{document.number:08d}.pdf",
                        content,
                        content_type="application/pdf",
                    ),
                },
            )
            document.representation_file = file
            document.save(update_fields=["representation_file"])
        return file, True
    except DatabaseError:
        if file is not None:
            cleanup_upload(file.storage_key)
        raise


def validate_representable(document):
    """
    Rechaza comprobantes que todavía no fueron emitidos. 
    @version 1.0
    @author Agustin
    """
    if document.status == InvoiceStatus.DRAFT:
        raise ValidationError({"status": "Sólo se representan comprobantes emitidos."})


def render_pdf(document):
    """
    Representa snapshots, ítems y totales históricos en un PDF paginado.
    No consulta datos actuales del emisor ni recalcula importes del comprobante.
    @version 1.0
    @author Agustin
    """
    is_credit_note = isinstance(document, CreditNote)
    title = (
        document.get_credit_note_type_display()
        if is_credit_note else document.get_invoice_type_display()
    )
    number = f"{document.point_of_sale.formatted_number}-{document.number:08d}"
    styles = getSampleStyleSheet()
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 12
    story = [Paragraph(escape(f"{title} {number}"), styles["Title"])]

    def text(label, value):
        """
        Agrega texto plano escapado, con salto de línea automático. 
        @version 1.0
        @author Agustin
        """
        story.append(Paragraph(
            escape(f"{label}: {value if value is not None else '-'}"),
            styles["BodyText"],
        ))

    text("Fecha de emisión", document.issue_date)
    story.append(Paragraph("Emisor", styles["Heading2"]))
    text("Razón social", document.issuer_legal_name)
    text("CUIT", document.issuer_tax_id)
    text("Domicilio", document.issuer_address)
    text("Condición IVA", document.get_issuer_vat_condition_display())
    text("Ingresos brutos", document.issuer_gross_income)
    text("Inicio de actividades", document.issuer_activity_start_date)
    story.append(Paragraph("Receptor", styles["Heading2"]))
    text("Nombre", document.receiver_name)
    text(document.get_receiver_document_type_display(), document.receiver_document_number)
    text("Domicilio", document.receiver_address)
    text("Condición IVA", document.get_receiver_vat_condition_display())
    if not is_credit_note:
        text("Concepto", document.get_concept_display())
        if document.service_date_from is not None:
            text("Servicio desde", document.service_date_from)
            text("Servicio hasta", document.service_date_to)
        if document.due_date is not None:
            text("Vencimiento", document.due_date)
        groups = [("Detalle", document.items.order_by("pk"))]
    else:
        groups = [
            (
                f"Factura {association.invoice.formatted_number} - Importe acreditado {association.total}",
                association.items.order_by("pk"),
            )
            for association in document.credit_note_invoices.select_related(
                "invoice__point_of_sale"
            ).order_by("pk")
        ]
    for heading, items in groups:
        story.append(Paragraph(escape(heading), styles["Heading2"]))
        rows = [["Descripción", "Cantidad", "Precio unit.", "Desc. %", "Tratamiento / IVA"]]
        for item in items:
            rows.append([
                item.description,
                str(item.quantity),
                str(item.unit_price),
                str(item.discount),
                f"{item.get_tax_treatment_display()} / {item.get_vat_rate_display() if item.vat_rate is not None else '-'}",
            ])
        table = LongTable(
            [[Paragraph(escape(cell), styles["BodyText"]) for cell in row] for row in rows],
            colWidths=[175, 55, 85, 50, 140],
            repeatRows=1,
            style=[
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf2")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.grey),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ],
        )
        story.extend([table, Spacer(1, 12)])
    story.append(Paragraph("Totales", styles["Heading2"]))
    for label, field in (
        ("Neto gravado", "net_taxed"), ("No gravado", "net_untaxed"),
        ("Exento", "net_exempt"), ("IVA", "vat_amount"), ("Total", "total"),
    ):
        text(label, getattr(document, field))
    if not is_credit_note:
        for tax in document.taxes.order_by("pk"):
            text(f"IVA {tax.get_vat_rate_display()} - Base {tax.base_amount}", tax.amount)
    story.append(Spacer(1, 16))
    story.append(Paragraph("Representación interna del comprobante. Sin autorización fiscal ARCA.", styles["BodyText"]))
    output = BytesIO()
    SimpleDocTemplate(
        output, pagesize=A4, title=f"{title} {number}",
        leftMargin=45, rightMargin=45, topMargin=36, bottomMargin=36,
    ).build(story)
    return output.getvalue()
