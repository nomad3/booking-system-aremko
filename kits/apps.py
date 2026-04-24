from django.apps import AppConfig


class KitsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'kits'
    verbose_name = 'Kits (productos compuestos)'

    def ready(self):
        # Importar signals al arrancar la app
        from . import signals  # noqa: F401
