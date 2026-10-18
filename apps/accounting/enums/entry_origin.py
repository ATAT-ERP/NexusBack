from django.db import models


class EntryOrigin(models.TextChoices):
    """
    Orígenes conocidos de los hechos contables.

    @version 1.0
    @author Agustin
    """

    MANUAL = "MANUAL"
    INVOICE = "INVOICE"
    PAYMENT = "PAYMENT"
    IMPORT = "IMPORT"
