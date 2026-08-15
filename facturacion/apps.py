from django.apps import AppConfig


class FacturacionConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'facturacion'
    verbose_name = 'Facturación electrónica SII (P-16, app aislada drift-safe)'

    def ready(self):
        from facturacion.medios import conectar_signals
        conectar_signals()
