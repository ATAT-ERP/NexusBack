from django.db import models


class User(models.Model):
    id = models.UUIDField(primary_key=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    avatar_path = models.CharField(max_length=500, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_system_admin = models.BooleanField(default=False)
