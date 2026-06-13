from django.contrib import admin
from solo.admin import SingletonModelAdmin

from .models import SugerenciaAgenteWhatsApp, WhatsAppAgentConfig


@admin.register(WhatsAppAgentConfig)
class WhatsAppAgentConfigAdmin(SingletonModelAdmin):
    fieldsets = (
        ('Control general', {
            'fields': ('activo', 'modo'),
            'description': 'Interruptor del agente y fase de operación. Empezar en "Borrador asistido".',
        }),
        ('Voz y derivación', {
            'fields': ('persona_tono', 'link_reserva'),
        }),
        ('Modelo (avanzado)', {
            'fields': ('model_name', 'temperature', 'max_tokens', 'history_window',
                       'pausa_horas_tras_humano'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('updated_at',)


@admin.register(SugerenciaAgenteWhatsApp)
class SugerenciaAgenteWhatsAppAdmin(admin.ModelAdmin):
    """Solo lectura: observabilidad de lo que el agente sugirió/escaló."""
    list_display = ('created_at', 'phone', 'escalar', 'enviada', 'modelo', 'output_tokens', 'latency_ms')
    list_filter = ('escalar', 'enviada', 'modo', 'modelo')
    search_fields = ('phone', 'wa_message_id', 'texto', 'motivo_escalar')
    readonly_fields = [f.name for f in SugerenciaAgenteWhatsApp._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
