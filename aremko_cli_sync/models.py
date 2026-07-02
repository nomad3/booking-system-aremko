"""Snapshot del reporte semanal de aremko-cli (gasto Google/Meta Ads por programa),
para mostrarlo en el dashboard de estadísticas de Django SIN llamar en vivo a
aremko-cli — su endpoint `GET /api/v1/brief/weekly` tarda ~50s porque llama en vivo
a Google Ads + Meta Ads + Django (confirmado 2026-07-01, curl real: 49.7s).

App AISLADA (drift-safe, mismo criterio que conciliacion/whatsapp_agent/
carrito_reservas/inbox_omnicanal): no toca los modelos de `ventas`.

Un management command (`sync_aremko_cli_weekly_brief`) corre 1 vez al día, disparado
por cron-job.org vía el endpoint `/ventas/api/cron/sync-aremko-cli-brief/`, y crea un
snapshot nuevo cada vez. El dashboard de estadísticas siempre lee el más reciente
(nunca llama a aremko-cli en el request-response de una página).
"""

from django.db import models


class WeeklyBriefSnapshot(models.Model):
    """Un snapshot del gasto en Ads por programa (Ritual/Refugio/Pausa — aremko-cli
    aún no mapea "Noche de Aguas Calientes"), semana a semana, tal como lo devuelve
    aremko-cli en `GET /api/v1/brief/weekly` (bloques `data.google_ads`/`data.meta_ads`).
    """

    fetched_at = models.DateTimeField(auto_now_add=True, db_index=True)
    success = models.BooleanField(
        default=False,
        help_text='True si el fetch a aremko-cli respondió 200 con datos utilizables.',
    )
    google_ads = models.JSONField(
        default=dict, blank=True,
        help_text='{"ritual": {"campaign_name", "weekly": [{label,spend,activity,reservas,ingresos}, ...]}, "refugio": {...}, "pausa": {...}}',
    )
    meta_ads = models.JSONField(
        default=dict, blank=True,
        help_text='Mismo shape que google_ads, para Meta Ads.',
    )
    error_message = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'aremko_cli_sync_weeklybriefsnapshot'
        verbose_name = 'Snapshot semanal aremko-cli'
        verbose_name_plural = 'Snapshots semanales aremko-cli'
        ordering = ['-fetched_at']

    def __str__(self):
        estado = 'OK' if self.success else 'ERROR'
        return f'Snapshot {self.fetched_at:%Y-%m-%d %H:%M} ({estado})'
