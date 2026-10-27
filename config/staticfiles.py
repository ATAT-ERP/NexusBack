from django.contrib.staticfiles.apps import StaticFilesConfig as DjangoStaticFilesConfig


class StaticFilesConfig(DjangoStaticFilesConfig):
    """Excluye los recursos de Browsable API durante cada collectstatic."""

    ignore_patterns = [*DjangoStaticFilesConfig.ignore_patterns, "rest_framework/*"]
