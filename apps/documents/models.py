import uuid

from django.db import models


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    name = models.CharField(max_length=255)
    original_name = models.CharField(max_length=255)
    storage_key = models.CharField(max_length=500)
    mime_type = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField()
    category_id = models.UUIDField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "documents"

