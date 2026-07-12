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


class PublicacionPlanificada(models.Model):
    """Una pieza de contenido concreta de la semana, con workflow de producción.

    Se genera automáticamente "explotando" el brief semanal (una fila por
    Reel/carrusel/story/GBP/email) para que Angélica (community manager)
    tenga una cola de trabajo clara: qué producir, con qué copy, en qué
    orden — y para poder colgarle métricas por publicación después.

    Fase 1 (2026-07-12): cola de trabajo + estados.
    Fase 2: material subido + revisión IA.
    Fase 3: métricas por publicación → decisiones Meta Ads.
    """

    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_produccion', 'En producción'),
        ('lista', 'Lista para publicar'),
        ('publicada', 'Publicada'),
        ('no_aplica', 'No aplica esta semana'),
    ]

    semana_inicio = models.DateField(db_index=True, help_text='Lunes de la semana del brief.')
    dia = models.DateField(db_index=True, help_text='Día planificado de publicación.')
    canal = models.CharField(max_length=40, help_text='Instagram | Instagram Stories | GBP | Email | Facebook')
    tipo = models.CharField(max_length=20, help_text='reel | carrusel | story | post | email')
    pieza_key = models.CharField(
        max_length=40,
        help_text='Clave de la pieza en el brief (gbp_post, reel_martes, story_lunes, ...). Única por semana.',
    )
    titulo = models.CharField(max_length=300, blank=True, default='', help_text='Concepto corto de la pieza.')
    copy_json = models.JSONField(
        default=dict, blank=True,
        help_text='La pieza completa del brief (guion, caption, hashtags, etc.) lista para usar.',
    )
    responsable = models.CharField(max_length=60, blank=True, default='')
    tiempo_estimado = models.CharField(max_length=60, blank=True, default='')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente', db_index=True)
    material_urls = models.JSONField(
        default=list, blank=True,
        help_text='URLs del material subido por Angélica (fotos/videos en Cloudinary). Fase 2.',
    )
    notas_revision = models.TextField(
        blank=True, default='',
        help_text='Feedback del revisor IA sobre el material subido. Fase 2.',
    )
    published_url = models.CharField(
        max_length=500, blank=True, default='',
        help_text='Link del post ya publicado (para colgarle métricas). Fase 3.',
    )
    metricas = models.JSONField(
        default=dict, blank=True,
        help_text='Métricas de la publicación, actualizadas semanalmente. Fase 3.',
    )
    notas = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'marketing_briefs_publicacionplanificada'
        verbose_name = 'Publicación planificada'
        verbose_name_plural = 'Publicaciones planificadas'
        ordering = ['dia', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['semana_inicio', 'pieza_key'],
                name='uniq_publicacion_semana_pieza',
            ),
        ]

    def __str__(self):
        return f'{self.dia} · {self.canal}/{self.tipo} · {self.get_estado_display()}'
