from django.db import models


class EntryStatus(models.TextChoices):
    """
    Estados admitidos para un asiento contable.

    @version 1.0
    @author Agustin
    """

    DRAFT = "DRAFT"
    POSTED = "POSTED"
    REVERSED = "REVERSED"
