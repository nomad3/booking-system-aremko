"""Archivo histórico de los briefs semanales de marketing.

App AISLADA (drift-safe, mismo criterio que aremko_cli_sync/kits/
conciliacion): no toca modelos de `ventas`. Antes de esto, el brief del
lunes solo se enviaba por email y se perdía — sin memoria de qué copy se
generó cada semana, el LLM repetía ganchos y no había forma de comparar
briefs entre semanas.

Se llena desde `generate_brief()` (marketing_brief_generator.py) con
try/except: si la tabla no existe todavía (migración pendiente) o falla el
guardado, el brief se genera y envía igual — el archivo nunca bloquea.
"""

from django.db import models


class WeeklyBriefArchive(models.Model):
    """Un brief semanal generado, completo, con sus ganchos extraídos.

    `ganchos` guarda las frases clave del copy generado (gancho de cada
    Reel, primera línea del GBP, asunto del email, hook del carrusel) para
    pasárselas al copywriter de la semana siguiente como "ya usado, no
    repetir" — la anti-repetición que el playbook pedía pero el LLM no
    podía cumplir sin memoria.
    """

    semana_inicio = models.DateField(
        db_index=True,
        help_text='Lunes de la semana a la que corresponde el brief.',
    )
    generated_at = models.DateTimeField(auto_now_add=True, db_index=True)
    model_analisis = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Modelo LLM usado para la pasada de análisis (llamada 1).',
    )
    model_copy = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Modelo LLM usado para la pasada de redacción (llamada 2).',
    )
    brief_json = models.JSONField(
        default=dict, blank=True,
        help_text='Brief completo (análisis + drafts ya fusionados), tal como se envió.',
    )
    ganchos = models.JSONField(
        default=list, blank=True,
        help_text='Frases clave del copy generado esta semana — insumo anti-repetición para la semana siguiente.',
    )
    exito = models.BooleanField(default=True)
    error = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'marketing_briefs_weeklybriefarchive'
        verbose_name = 'Brief semanal archivado'
        verbose_name_plural = 'Briefs semanales archivados'
        ordering = ['-generated_at']

    def __str__(self):
        estado = 'OK' if self.exito else 'ERROR'
        return f'Brief {self.semana_inicio} ({estado})'
