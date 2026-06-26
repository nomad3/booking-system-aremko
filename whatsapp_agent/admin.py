from django.contrib import admin
from solo.admin import SingletonModelAdmin

from .models import (
    AgenteFeedback, AusenciaEnviada, PropuestaReserva, SugerenciaAgenteWhatsApp,
    SugerenciaAprendizaje, WhatsAppAgentConfig,
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
        ('Servicios complementarios (no se ofrecen como principales)', {
            'fields': ('servicios_complementarios',),
            'description': 'Mueve a la derecha las tinas/servicios que son COMPLEMENTO (niño, '
                           'tina fría, decoraciones): se agregan a una reserva pero el agente NO '
                           'los ofrece solos ni los lista en disponibilidad.',
        }),
        ('Costos / Métricas', {
            'fields': ('tarifa_plantilla_clp',),
            'description': 'Costo por mensaje de plantilla de marketing (WhatsApp), en CLP. Lo usa el '
                           'tablero de Métricas para estimar el costo de las campañas (las respuestas '
                           'del agente dentro de las 24h son gratis). 0 = sin configurar → costo nulo.',
        }),
        ('Modelo y parámetros LLM', {
            'fields': ('model_name', 'temperature', 'max_tokens', 'history_window',
                       'pausa_horas_tras_humano'),
            'description': 'model_name vacío = usa DPV_LLM_MODEL de env. Ej: anthropic/claude-haiku-4.5 o google/gemini-3.1-flash-tts-preview',
        }),
    )
    readonly_fields = ('updated_at',)
    filter_horizontal = ('servicios_complementarios',)


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


@admin.register(SugerenciaAprendizaje)
class SugerenciaAprendizajeAdmin(admin.ModelAdmin):
    """Correcciones clasificadas (H-010 p2). Editable el estado para aprobar/descartar a mano."""
    list_display = ('created_at', 'phone', 'tipo', 'estado', 'texto_propuesto')
    list_filter = ('estado', 'tipo')
    search_fields = ('phone', 'texto_propuesto', 'ref_catalogo', 'borrador', 'enviado')
    readonly_fields = ('feedback', 'phone', 'tipo', 'ref_catalogo', 'motivo', 'borrador',
                       'enviado', 'modelo', 'created_at', 'resuelto_at', 'aplicado_info')


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


@admin.register(PropuestaReserva)
class PropuestaReservaAdmin(admin.ModelAdmin):
    """Propuestas de Luna. Link clickeable a la cotización del cliente (Fase 3)."""
    list_display = ('propuesta_id_corto', 'external_id', 'total', 'estado', 'cotizacion_link', 'created_at')
    list_filter = ('estado', 'canal')
    search_fields = ('propuesta_id', 'external_id')
    ordering = ('-id',)

    def propuesta_id_corto(self, obj):
        return (obj.propuesta_id or '')[:8]
    propuesta_id_corto.short_description = 'Propuesta'

    def cotizacion_link(self, obj):
        from django.utils.html import format_html
        from ventas.views.ficha_reserva_view import url_cotizacion
        if not obj.propuesta_id or obj.estado != 'pendiente':
            return '—'
        url = url_cotizacion(obj.propuesta_id)
        return format_html('<a class="button" href="{}" target="_blank">🌙 Cotización</a>', url)
    cotizacion_link.short_description = 'Cotización cliente'
