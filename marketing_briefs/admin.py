from django.contrib import admin

from .models import PublicacionPlanificada, WeeklyBriefArchive


@admin.register(PublicacionPlanificada)
class PublicacionPlanificadaAdmin(admin.ModelAdmin):
    """Cola de publicaciones de la semana. La interfaz principal de Angélica
    vive en aremko-cli; este admin es el respaldo/supervisión de Jorge."""

    list_display = ('dia', 'canal', 'tipo', 'titulo_corto', 'responsable', 'estado', 'updated_at')
    list_filter = ('estado', 'canal', 'tipo', 'semana_inicio')
    search_fields = ('titulo', 'pieza_key')
    date_hierarchy = 'semana_inicio'
    list_editable = ('estado',)

    def titulo_corto(self, obj):
        return (obj.titulo or obj.pieza_key)[:60]
    titulo_corto.short_description = 'Título'


@admin.register(WeeklyBriefArchive)
class WeeklyBriefArchiveAdmin(admin.ModelAdmin):
    """Solo lectura en la práctica: los briefs los crea el cron del lunes.

    Útil para revisar drafts históricos sin buscar emails, y para ver qué
    ganchos se le pasaron al copywriter como "ya usados".
    """

    list_display = ('semana_inicio', 'generated_at', 'exito', 'model_analisis', 'model_copy')
    list_filter = ('exito',)
    date_hierarchy = 'semana_inicio'
    readonly_fields = (
        'semana_inicio', 'generated_at', 'model_analisis', 'model_copy',
        'brief_json', 'ganchos', 'exito', 'error',
    )

    def has_add_permission(self, request):
        return False
