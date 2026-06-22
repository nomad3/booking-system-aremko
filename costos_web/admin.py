# -*- coding: utf-8 -*-
from django.contrib import admin
from django.utils.html import format_html

from .models import ServicioWeb

_COLOR = {
    'vencido':  ('#b91c1c', '#fee2e2', 'VENCIDO'),
    'urgente':  ('#b45309', '#fef3c7', '≤ 7 días'),
    'pronto':   ('#854d0e', '#fefce8', '≤ 15 días'),
    'ok':       ('#15803d', '#dcfce7', 'OK'),
    'sin_fecha': ('#6b7280', '#f3f4f6', '— sin fecha'),
}


def _badge(texto, fg, bg):
    return format_html(
        '<span style="background:{};color:{};padding:2px 9px;border-radius:999px;'
        'font-weight:600;font-size:12px;white-space:nowrap;">{}</span>', bg, fg, texto)


@admin.register(ServicioWeb)
class ServicioWebAdmin(admin.ModelAdmin):
    """Tablero de costos — visible y editable SOLO por superusuarios."""
    list_display = ('nombre', 'categoria', 'modalidad', 'monto_col',
                    'proxima_fecha_pago', 'vencimiento_col', 'tarjeta_col', 'saldo_col', 'activo')
    list_filter = ('categoria', 'modalidad', 'activo', 'moneda')
    search_fields = ('nombre', 'responsable', 'notas')
    ordering = ('proxima_fecha_pago', 'nombre')
    list_per_page = 100

    fieldsets = (
        ('Servicio', {
            'fields': ('nombre', 'categoria', 'modalidad', 'activo', 'url_facturacion', 'responsable')
        }),
        ('Costo y fechas', {
            'fields': ('monto', 'moneda', 'ciclo', 'proxima_fecha_pago', 'ultima_fecha_pago')
        }),
        ('Tarjeta (solo últimos 4 dígitos)', {
            'fields': ('tarjeta_ultimos4', 'tarjeta_banco'),
            'description': '⚠️ NUNCA guardar el número completo, CVV ni vencimiento de la tarjeta. '
                           'Solo los últimos 4 dígitos para identificarla.'
        }),
        ('Saldo (solo servicios de uso/prepago)', {
            'fields': ('saldo_actual', 'saldo_umbral_alerta', 'saldo_actualizado'),
            'description': 'Para los servicios que se pagan por uso/recarga: saldo disponible y '
                           'el umbral bajo el cual quieres que se marque en rojo.'
        }),
        ('Notas', {'fields': ('notas',)}),
    )
    readonly_fields = ()

    # --- Acceso SOLO superusuarios ---
    def has_module_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    # --- Columnas con formato ---
    @admin.display(description='Monto')
    def monto_col(self, obj):
        if obj.monto is None:
            return '—'
        ciclo = dict(ServicioWeb.CICLOS).get(obj.ciclo, obj.ciclo)
        return f'{obj.monto:,.0f} {obj.moneda} / {ciclo.lower()}'

    @admin.display(description='Vencimiento')
    def vencimiento_col(self, obj):
        fg, bg, etiqueta = _COLOR.get(obj.estado_pago, _COLOR['sin_fecha'])
        d = obj.dias_para_pago
        if d is not None:
            etiqueta = f'{etiqueta} ({d}d)' if obj.estado_pago != 'vencido' else f'VENCIDO ({-d}d)'
        return _badge(etiqueta, fg, bg)

    @admin.display(description='Tarjeta')
    def tarjeta_col(self, obj):
        if not obj.tarjeta_ultimos4:
            return '—'
        banco = f' · {obj.tarjeta_banco}' if obj.tarjeta_banco else ''
        return f'****{obj.tarjeta_ultimos4}{banco}'

    @admin.display(description='Saldo')
    def saldo_col(self, obj):
        if obj.modalidad != 'uso' or obj.saldo_actual is None:
            return '—'
        txt = f'{obj.saldo_actual:,.0f} {obj.moneda}'
        if obj.saldo_bajo:
            return _badge(f'{txt} ⚠️ bajo', '#b91c1c', '#fee2e2')
        return _badge(txt, '#15803d', '#dcfce7')
