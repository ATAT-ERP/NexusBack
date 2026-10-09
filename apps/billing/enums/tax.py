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


class VATRate(models.IntegerChoices):
    """
    Alícuotas de IVA soportadas con los códigos oficiales de ARCA.
    @version 1.0
    @author Uziel
    """

    ZERO = 3, "0%"
    TWO_AND_HALF = 9, "2,5%"
    FIVE = 8, "5%"
    TEN_AND_HALF = 4, "10,5%"
    TWENTY_ONE = 5, "21%"
    TWENTY_SEVEN = 6, "27%"


class TaxTreatment(models.TextChoices):
    """
    Tratamiento fiscal de un ítem, que se usa junto con la alícuota de
    IVA. No tiene código fiscal: es una clasificación propia de A.T.A.T.
    @version 1.0
    @author Uziel
    """

    TAXED = "taxed"
    EXEMPT = "exempt"
    UNTAXED = "untaxed"
    NOT_DISCRIMINATED = "not_discriminated"
