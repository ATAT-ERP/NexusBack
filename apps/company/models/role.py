from django.db import models


class CompanyRole(models.Model):
    """
    Define un rol dentro de una compañía.

    @version 1.0
    @author Agustin
    """

    code = models.CharField(max_length=20, unique=True)
