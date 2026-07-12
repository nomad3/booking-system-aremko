from django.contrib import admin
from django.utils.html import format_html

from .models import (BoletaElectronica, ConfiguracionFacturacion, MedioPago,
                     RangoFolios)
from .services.emisor import emitir_boleta_para_pago


@admin.register(MedioPago)
class MedioPagoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'genera_boleta', 'nota', 'actualizado_at')
    list_editable = ('genera_boleta',)
    list_filter = ('genera_boleta',)
    search_fields = ('codigo', 'nombre')
    ordering = ('-genera_boleta', 'codigo')


@admin.register(ConfiguracionFacturacion)
class ConfiguracionFacturacionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'ambiente', 'emision_automatica', 'rut_emisor', 'actualizado_at')

    fieldsets = (
        ('Operación', {
            'fields': ('ambiente', 'emision_automatica'),
            'description': ("Las credenciales (API key SimpleAPI, certificado .pfx y su clave) "
                            "NO van aquí: viven en variables de entorno de Render "
                            "(SIMPLEAPI_API_KEY, SII_CERT_B64, SII_CERT_PASSWORD)."),
        }),
        ('Datos del emisor (van impresos en cada boleta)', {
            'fields': ('rut_emisor', 'razon_social', 'giro_boleta', 'direccion',
                       'comuna', 'indicador_servicio', 'rut_firmante'),
        }),
    )

    def has_add_permission(self, request):
        return not ConfiguracionFacturacion.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RangoFolios)
class RangoFoliosAdmin(admin.ModelAdmin):
    list_display = ('tipo_dte', 'ambiente', 'folio_desde', 'folio_hasta',
                    'folio_siguiente', 'restantes_col', 'activo', 'creado_at')
    list_filter = ('ambiente', 'tipo_dte', 'activo')

    def restantes_col(self, obj):
        color = '#1e7d32' if obj.restantes > 50 else '#c62828'
        return format_html('<b style="color:{}">{}</b>', color, obj.restantes)
    restantes_col.short_description = 'Folios restantes'


@admin.register(BoletaElectronica)
class BoletaElectronicaAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'estado_badge', 'ambiente', 'caso_set', 'folio',
                    'reserva_link', 'metodo_pago_col', 'monto_total', 'track_id',
                    'emitida_at', 'creada_at')
    list_filter = ('estado', 'ambiente', 'tipo_dte', 'caso_set')
    search_fields = ('folio', 'venta_reserva__id', 'pago__id', 'glosa')
    date_hierarchy = 'creada_at'
    actions = ['reintentar_emision']
    readonly_fields = ('pago', 'venta_reserva', 'tipo_dte', 'ambiente', 'folio',
                       'monto_total', 'monto_neto', 'monto_iva', 'glosa', 'estado',
                       'track_id', 'error_mensaje', 'intentos', 'token_consulta',
                       'creada_at', 'emitida_at', 'actualizada_at', 'xml_resumen')
    exclude = ('xml_dte',)

    def has_add_permission(self, request):
        # Las boletas nacen desde los pagos (acción en Pagos o emisión automática F2).
        return False

    def has_delete_permission(self, request, obj=None):
        # Solo se pueden borrar boletas sin valor tributario (para reintentar limpio).
        if obj is None:
            return request.user.is_superuser
        return request.user.is_superuser and obj.estado in ('pendiente', 'simulada', 'error')

    ESTADO_COLORES = {
        'simulada': '#616161', 'generada': '#1565c0', 'enviada': '#6a1b9a',
        'aceptada': '#1e7d32', 'rechazada': '#c62828', 'error': '#c62828',
        'pendiente': '#8d6e63', 'anulada': '#37474f',
    }

    def estado_badge(self, obj):
        color = self.ESTADO_COLORES.get(obj.estado, '#616161')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;'
            'font-size:11px">{}</span>', color, obj.get_estado_display())
    estado_badge.short_description = 'Estado'

    def reserva_link(self, obj):
        if not obj.venta_reserva_id:
            return '-'
        return format_html('<a href="/admin/ventas/ventareserva/{}/change/">Reserva #{}</a>',
                           obj.venta_reserva_id, obj.venta_reserva_id)
    reserva_link.short_description = 'Reserva'

    def metodo_pago_col(self, obj):
        return obj.pago.metodo_pago if obj.pago_id else '-'
    metodo_pago_col.short_description = 'Medio de pago'

    def xml_resumen(self, obj):
        if not obj.xml_dte:
            return '(sin XML todavía)'
        return format_html('<textarea readonly rows="12" style="width:100%">{}</textarea>',
                           obj.xml_dte[:8000])
    xml_resumen.short_description = 'XML del DTE'

    @admin.action(description='Reintentar emisión (boletas con error)')
    def reintentar_emision(self, request, queryset):
        ok, saltadas = 0, 0
        for boleta in queryset:
            if boleta.estado not in ('error', 'pendiente'):
                saltadas += 1
                continue
            _, mensaje = emitir_boleta_para_pago(boleta.pago)
            ok += 1
            self.message_user(request, f"Boleta de pago #{boleta.pago_id}: {mensaje}")
        if saltadas:
            self.message_user(request, f"{saltadas} boleta(s) ya definitivas — no se tocaron.")
