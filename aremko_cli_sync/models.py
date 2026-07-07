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


class SEORankingSnapshot(models.Model):
    """Snapshot histórico del rank-check SEO (DataForSEO, vía aremko-cli
    `GET /api/v1/seo/rankings`), una fila por keyword por corrida.

    El endpoint en vivo de aremko-cli solo da la foto del momento (cacheada
    12h en memoria, se pierde en cada redeploy de Render) — este modelo
    permite ver la evolución de la posición orgánica de cada keyword en el
    tiempo, no solo el estado actual. Mismo espíritu que `WeeklyBriefSnapshot`
    (app aislada, drift-safe, no toca modelos de `ventas`).

    Se llena vía `sync_aremko_cli_seo_rankings` — una corrida crea N filas
    (una por keyword de la lista fija documentada en docs/LOOP_SEO.md, hoy 8).
    """

    fetched_at = models.DateTimeField(auto_now_add=True, db_index=True)
    success = models.BooleanField(
        default=False,
        help_text='True si el fetch a aremko-cli respondió 200 con datos utilizables para esta keyword.',
    )
    keyword = models.CharField(max_length=200, db_index=True, blank=True, default='')
    target_domain = models.CharField(max_length=200, blank=True, default='aremko.cl')
    location_name = models.CharField(
        max_length=100, blank=True, default='',
        help_text='location_name de DataForSEO usado en este check (ej. "Puerto Varas,Los Lagos,Chile").',
    )
    found = models.BooleanField(default=False)
    position = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Posición ORGÁNICA (cuenta solo resultados type=organic, 1-indexed). Null si no encontrado.',
    )
    rank_absolute = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Posición absoluta en el SERP completo (incluye knowledge graph, imágenes, local pack, etc. antes) — referencia, no usar para comparar ciclo a ciclo.',
    )
    url = models.CharField(max_length=500, blank=True, default='')
    competitors_above = models.JSONField(
        default=list, blank=True,
        help_text='Dominios orgánicos que aparecen antes del target (máx 10) para esta keyword.',
    )
    error_message = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'aremko_cli_sync_seorankingsnapshot'
        verbose_name = 'Snapshot ranking SEO (aremko-cli)'
        verbose_name_plural = 'Snapshots ranking SEO (aremko-cli)'
        ordering = ['-fetched_at']
        indexes = [
            models.Index(fields=['keyword', '-fetched_at']),
        ]

    def __str__(self):
        if not self.success:
            return f'{self.keyword or "?"} — ERROR ({self.fetched_at:%Y-%m-%d})'
        estado = f'pos {self.position}' if self.found else 'no encontrado'
        return f'{self.keyword} — {estado} ({self.fetched_at:%Y-%m-%d})'
