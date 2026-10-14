from django.db import models


class Currency(models.TextChoices):
    """
    Códigos de moneda reconocidos por Accounting.

    @version 1.0
    @author Agustin
    """

    ARS = "ARS"
