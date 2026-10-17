from django.db import models


class InvoiceType(models.IntegerChoices):
    """
    Tipos de comprobante soportados, usando el código fiscal AFIP
    correspondiente como valor del enum.
    @version 1.0
    @author Thiago
    """

    INVOICE_A = 1, "Factura A"
    INVOICE_B = 6, "Factura B"
    INVOICE_C = 11, "Factura C"


class CreditNoteType(models.IntegerChoices):
    """
    Tipos de Nota de Crédito soportados, usando el código fiscal AFIP
    correspondiente como valor del enum.
    @version 1.0
    @author Uziel
    """

    CREDIT_NOTE_A = 3, "Nota de Crédito A"
    CREDIT_NOTE_B = 8, "Nota de Crédito B"
    CREDIT_NOTE_C = 13, "Nota de Crédito C"


INVOICE_TYPE_BY_CREDIT_NOTE_TYPE = {
    CreditNoteType.CREDIT_NOTE_A: InvoiceType.INVOICE_A,
    CreditNoteType.CREDIT_NOTE_B: InvoiceType.INVOICE_B,
    CreditNoteType.CREDIT_NOTE_C: InvoiceType.INVOICE_C,
}


class InvoiceConcept(models.IntegerChoices):
    """
    Concepto del comprobante, usando el código fiscal AFIP/ARCA
    correspondiente como valor del enum.
    @version 1.0
    @author Uziel
    """

    PRODUCTS = 1, "Productos"
    SERVICES = 2, "Servicios"
    PRODUCTS_AND_SERVICES = 3, "Productos y Servicios"


class InvoiceStatus(models.TextChoices):
    """
    Estado interno del comprobante. No tiene código fiscal: es un
    estado propio de A.T.A.T.
    @version 1.0
    @author Uziel
    """

    DRAFT = "draft"
    ISSUED = "issued"
    CANCELLED = "cancelled"


class DocumentType(models.IntegerChoices):
    """
    Tipo de documento del receptor, usando el código fiscal AFIP/ARCA
    correspondiente como valor del enum.
    @version 1.0
    @author Uziel
    """

    CUIT = 80, "CUIT"
    CUIL = 86, "CUIL"
    CDI = 87, "CDI"
    DNI = 96, "DNI"
