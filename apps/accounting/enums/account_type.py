from django.db import models


class AccountType(models.TextChoices):
    """
    Tipos de cuenta admitidos por Accounting.

    @version 1.0
    @author Agustin
    """

    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"
