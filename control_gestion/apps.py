from django.apps import AppConfig


class ControlGestionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'control_gestion'
    verbose_name = 'Control de Gestión'

    def ready(self):
        """Importar signals cuando la app esté lista"""
        import control_gestion.signals

