# ventas/apps.py

from django.apps import AppConfig

class VentasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ventas'
    verbose_name = 'Ventas y CRM' # Optional: Set a more descriptive name for the admin

    def ready(self):
        # Importar triggers de comunicación para registrar señales (post_save VentaReserva)
        # Nota: mantener este import aquí para garantizar el registro en arranque
        try:
            import ventas.services.communication_triggers  # noqa: F401
        except Exception as exc:
            # Loguear, pero no romper el arranque del proyecto
            from django.conf import settings
            import logging
            logging.getLogger(__name__).warning(
                f"No se pudo importar communication_triggers: {exc}"
            )

        # Importar signals principales (validar_disponibilidad, actualizar_tramo, etc.)
        try:
            import ventas.signals.main_signals  # noqa: F401
        except Exception as exc:
            from django.conf import settings
            import logging
            logging.getLogger(__name__).warning(
                f"No se pudo importar main_signals: {exc}"
            )

        # Importar signals de GiftCards (post_save Pago)
        try:
            import ventas.signals.giftcard_signals  # noqa: F401
        except Exception as exc:
            from django.conf import settings
            import logging
            logging.getLogger(__name__).warning(
                f"No se pudo importar giftcard_signals: {exc}"
            )

        # Los modelos ya están registrados en admin.py usando decoradores @admin.register
        # No necesitamos registrarlos manualmente aquí
        # Importar admin para asegurar que se ejecuten los decoradores
        from . import admin as ventas_admin  # noqa: F401
