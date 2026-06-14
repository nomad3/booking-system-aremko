from django.contrib import admin
from solo.admin import SingletonModelAdmin

from .models import (
    AgenteFeedback, AusenciaEnviada, SugerenciaAgenteWhatsApp, WhatsAppAgentConfig,
)


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
        ('Conocimiento y correcciones (autoridad máxima)', {
            'fields': ('conocimiento',),
            'description': 'Reglas que el agente respeta SIEMPRE, por sobre el catálogo. Una por línea. '
                           'Ej: "Las tinas se cobran por persona, capacidad 1-4." / "No ofrecer Cacao."',
        }),
        ('Mensaje de ausencia', {
            'fields': ('ausencia_activa', 'ausencia_mensaje', 'ausencia_anti_spam_horas'),
            'description': 'Si se activa, a cada cliente que escribe se le responde la frase fija '
                           'y NO se genera borrador del agente (precedencia).',
        }),
        ('Modelo (avanzado)', {
            'fields': ('model_name', 'temperature', 'max_tokens', 'history_window',
                       'pausa_horas_tras_humano'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('updated_at',)


@admin.register(AgenteFeedback)
class AgenteFeedbackAdmin(admin.ModelAdmin):
    """Solo lectura: delta borrador-vs-enviado (motor de aprendizaje H-010)."""
    list_display = ('created_at', 'phone', 'editado', 'procesado')
    list_filter = ('editado', 'procesado')
    search_fields = ('phone', 'wa_message_id', 'borrador', 'enviado')
    readonly_fields = [f.name for f in AgenteFeedback._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AusenciaEnviada)
class AusenciaEnviadaAdmin(admin.ModelAdmin):
    list_display = ('phone', 'ultimo_envio')
    search_fields = ('phone',)
    readonly_fields = ('phone', 'ultimo_envio')

    def has_add_permission(self, request):
        return False


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
