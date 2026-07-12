from django.contrib import admin

from .models import WeeklyBriefArchive


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
