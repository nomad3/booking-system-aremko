from django.apps import AppConfig


class ArtesaniasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'artesanias'
    verbose_name = 'Artesanías (sala de ventas)'

    def ready(self):
        from . import signals  # noqa: F401 — conecta el deshacer automático
