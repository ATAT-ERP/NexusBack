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