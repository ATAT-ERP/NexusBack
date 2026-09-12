import re
import uuid

from django.db import models


class Company(models.Model):
    class Type(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        ORGANIZATION = "organization", "Organization"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.INDIVIDUAL,
    )
    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True, null=True)
    tax_id = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    address_street = models.CharField(max_length=255, blank=True, null=True)
    address_number = models.CharField(max_length=20, blank=True, null=True)
    address_city = models.CharField(max_length=100, blank=True, null=True)
    address_postal_code = models.CharField(max_length=20, blank=True, null=True)
    address_province = models.CharField(max_length=100, blank=True, null=True)
    address_country = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "companies"
        constraints = [
            models.UniqueConstraint(
                fields=["tax_id"],
                name="unique_company_tax_id",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.tax_id is not None:
            self.tax_id = normalize_tax_id(self.tax_id) or None
        super().save(*args, **kwargs)


_TAX_ID_WEIGHTS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def normalize_tax_id(value):
    """Normaliza un CUIT/CUIL eliminando guiones, puntos y espacios."""
    if value is None:
        return None
    return re.sub(r"[\s.\-]", "", value)


def is_valid_tax_id(value):
    """Indica si un CUIT/CUIL es estructuralmente válido.

    Sólo comprueba la estructura local y el dígito verificador. No verifica la
    existencia ni el estado del identificador ante ARCA.
    """
    digits = normalize_tax_id(value)
    if digits is None:
        return False
    if not digits.isdigit() or len(digits) != 11:
        return False

    body = digits[:10]
    check = int(digits[10])

    total = sum(int(d) * w for d, w in zip(body, _TAX_ID_WEIGHTS))
    remainder = total % 11
    if remainder == 0:
        expected = 0
    elif remainder == 1:
        expected = 9
    else:
        expected = 11 - remainder

    return check == expected
