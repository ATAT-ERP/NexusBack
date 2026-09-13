from django.db import models


class CompanyMember(models.Model):
    """
    Relaciona un usuario, una compañía y su rol.

    @version 1.0
    @author Agustin
    """

    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="company_memberships",
    )
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.ForeignKey(
        "companies.CompanyRole",
        on_delete=models.PROTECT,
        related_name="memberships",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "company"],
                name="unique_company_membership",
            ),
        ]
