from django.db import models


class PointOfSale(models.Model):
    """
    Punto de venta propio de un perfil fiscal. El número se asigna
    automáticamente (ver services/numbering.py) y nunca se solicita
    al usuario.
    @version 1.0
    @author Thiago
    """

    fiscal_profile = models.ForeignKey(
        "billing.FiscalProfile",
        on_delete=models.CASCADE,
        related_name="points_of_sale",
    )
    number = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "billing_points_of_sale"
        constraints = [
            models.UniqueConstraint(
                fields=["fiscal_profile", "number"],
                name="unique_point_of_sale_number_per_fiscal_profile",
            )
        ]

    @property
    def formatted_number(self):
        """
        Representa el número de punto de venta con cinco dígitos.
        @version 1.0
        @author Thiago
        """
        return f"{self.number:05d}"

    def __str__(self):
        return f"PointOfSale({self.fiscal_profile_id}, {self.formatted_number})"