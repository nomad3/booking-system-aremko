from django.apps import AppConfig


class PersonalOperativoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'personal_operativo'
    verbose_name = 'Personal Operativo (Luna Interna)'

    def ready(self):
        # Conecta el signal que avisa al recepcionista de turno cuando se crea
        # una tarea de Recepción/Operación en control_gestion (Fase 2).
        from . import signals  # noqa: F401
