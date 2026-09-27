from django.apps import AppConfig


class CloudConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cloud"
    # Keep the historical migration label so existing applied migrations are reused.
    label = "documents"
