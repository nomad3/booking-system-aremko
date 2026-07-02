from django.apps import AppConfig


class AremkoCliSyncConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'aremko_cli_sync'
    verbose_name = 'Sincronización con aremko-cli (H-058, app aislada drift-safe)'
