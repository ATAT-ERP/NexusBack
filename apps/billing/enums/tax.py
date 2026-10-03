from django.db import models


class VATCondition(models.IntegerChoices):
    """
    Condiciones frente al IVA con los códigos oficiales de ARCA.
    """
    REGISTERED_RESPONSIBLE = 1, "IVA Responsable Inscripto"
    EXEMPT = 4, "IVA Sujeto Exento"
    FINAL_CONSUMER = 5, "Consumidor Final"
    MONOTAX = 6, "Responsable Monotributo"
    SOCIAL_MONOTAX = 13, "Monotributista Social"
    NOT_SUBJECT = 15, "IVA No Alcanzado"
    PROMOTED_INDEPENDENT_WORKER = 16, "Monotributo Trabajador Independiente Promovido"