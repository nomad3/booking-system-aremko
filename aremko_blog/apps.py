from django.apps import AppConfig


class AremkoBlogConfig(AppConfig):
    """Blog editorial de aremko.cl.

    App aislada (no importa de `ventas/` ni `destino_puerto_varas/`) para que
    el día que DPV se migre a su propio Render service, este blog quede
    intacto. Mirrors del patrón DPV-SEO-002 #6 con voz/clusters propios.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "aremko_blog"
    verbose_name = "Aremko · Blog editorial"
