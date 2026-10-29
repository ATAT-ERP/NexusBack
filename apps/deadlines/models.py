import uuid

from django.db import models


class Deadline(models.Model):
    """
    Tarea o vencimiento de un usuario para una compañía.
    @version 1.0
    @author Agustin
    """

    class Status(models.TextChoices):
        PENDING = "pending"
        COMPLETED = "completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="deadlines")
    company = models.ForeignKey(
        "companies.Company", on_delete=models.PROTECT, related_name="deadlines"
    )
    name = models.CharField(max_length=255)
    period = models.CharField(max_length=255, blank=True, null=True)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "deadlines"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["pending", "completed"]),
                name="deadline_valid_status",
            ),
        ]
