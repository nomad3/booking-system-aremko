"""Admin de conciliación: auditoría (ReconciliacionLog) + Conciliador F1 para
Deborah (MovimientoMP: traer pagos de MP con un botón, confirmar sugerencias
con 1 clic). Funcionalidad como formularios admin, no CLI (regla del proyecto)."""

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path

from .models import MovimientoMP, ReconciliacionLog
from .services_mp import aplicar_movimiento, matchear_movimiento, traer_pagos_mp


@admin.register(ReconciliacionLog)
class ReconciliacionLogAdmin(admin.ModelAdmin):
    list_display = ('referencia', 'reserva', 'monto', 'metodo_pago', 'origen',
                    'actor', 'estado', 'fecha_movimiento', 'creado_en')
    list_filter = ('estado', 'origen', 'metodo_pago', 'actor')
    search_fields = ('referencia', 'reserva__id', 'notas')
    date_hierarchy = 'creado_en'
    ordering = ('-creado_en',)
    readonly_fields = ('referencia', 'reserva', 'pago', 'monto', 'metodo_pago', 'origen',
                       'actor', 'fecha_movimiento', 'payload', 'estado', 'notas', 'creado_en')

    def has_add_permission(self, request):
        # Las conciliaciones solo se crean por API (AgentProvision), nunca a mano.
        return False

    def has_delete_permission(self, request, obj=None):
        # Log de auditoría: no se borra.
        return False


@admin.register(MovimientoMP)
class MovimientoMPAdmin(admin.ModelAdmin):
    """Cola de conciliación para Deborah (arranque supervisado).

    Flujo: botón "Traer pagos de MP" → los nuevos llegan con sugerencia del
    matcher → seleccionar filas → acción "✅ Aplicar a la reserva sugerida".
    Si la sugerencia está mal: abrir el movimiento, cambiar el campo
    "Sugerencia" (lupa) y aplicar. Lo que no corresponde a reservas → "Ignorar".
    """

    list_display = ('fecha', 'monto_fmt', 'tipo_corto', 'glosa', 'estado',
                    'sugerencia_link', 'sugerencia_motivo')
    list_filter = ('estado', 'tipo')
    search_fields = ('mp_payment_id', 'transaction_id', 'glosa',
                     'sugerencia__id', 'sugerencia__cliente__nombre')
    date_hierarchy = 'fecha'
    ordering = ('-fecha',)
    raw_id_fields = ('sugerencia',)
    readonly_fields = ('mp_payment_id', 'fecha', 'monto', 'tipo', 'glosa',
                       'transaction_id', 'payer_email', 'external_reference',
                       'estado', 'reserva_aplicada', 'sugerencia_motivo',
                       'raw', 'creado_en', 'actualizado_en')
    actions = ('aplicar_a_sugerida', 'recalcular_sugerencia', 'ignorar')
    list_per_page = 50

    # ── columnas ──
    @admin.display(description='Monto', ordering='monto')
    def monto_fmt(self, obj):
        return f'${int(obj.monto):,}'.replace(',', '.')

    @admin.display(description='Tipo')
    def tipo_corto(self, obj):
        return {'account_fund/bank_transfer': '🏦 transferencia',
                'money_transfer/account_money': '💰 saldo MP'}.get(
                    obj.tipo, obj.tipo.split('/')[-1] or obj.tipo)

    @admin.display(description='Reserva sugerida')
    def sugerencia_link(self, obj):
        reserva = obj.reserva_aplicada or obj.sugerencia
        if not reserva:
            return '—'
        from django.utils.html import format_html
        cliente = reserva.cliente.nombre if reserva.cliente else '(sin cliente)'
        return format_html(
            '<a href="/admin/ventas/ventareserva/{}/change/" target="_blank">#{} · {} · saldo ${}</a>',
            reserva.id, reserva.id, cliente,
            f'{int(reserva.saldo_pendiente or 0):,}'.replace(',', '.'))

    # ── botón "Traer pagos de MP" ──
    def get_urls(self):
        urls = super().get_urls()
        extra = [path('traer/', self.admin_site.admin_view(self.traer_pagos_view),
                      name='conciliacion_movimientomp_traer')]
        return extra + urls

    def traer_pagos_view(self, request):
        try:
            nuevos, total_api = traer_pagos_mp(dias=14)
            sugeridos = sum(1 for m in nuevos if m.estado == 'sugerido')
            messages.success(
                request,
                f'MP devolvió {total_api} pagos (14 días): {len(nuevos)} nuevos '
                f'({sugeridos} con sugerencia, {len(nuevos) - sugeridos} a revisar).')
        except Exception as e:
            messages.error(request, f'Error consultando Mercado Pago: {e}')
        return redirect('admin:conciliacion_movimientomp_changelist')

    # ── acciones ──
    @admin.action(description='✅ Aplicar a la reserva sugerida (crea el pago)')
    def aplicar_a_sugerida(self, request, queryset):
        aplicados, errores = 0, 0
        for mov in queryset.select_related('sugerencia'):
            if mov.estado == 'aplicado':
                continue
            if not mov.sugerencia:
                messages.warning(request, f'{mov} no tiene reserva sugerida — ábrelo y asigna una.')
                errores += 1
                continue
            try:
                ok, msg = aplicar_movimiento(mov, mov.sugerencia,
                                             actor=request.user.username or 'admin')
            except Exception as e:
                ok, msg = False, str(e)
            if ok:
                aplicados += 1
                messages.success(request, msg)
            else:
                errores += 1
                messages.error(request, f'{mov}: {msg}')
        if aplicados:
            messages.success(request, f'{aplicados} pago(s) aplicado(s) y auditado(s).')

    @admin.action(description='🔄 Recalcular sugerencia')
    def recalcular_sugerencia(self, request, queryset):
        n = 0
        for mov in queryset.exclude(estado__in=('aplicado', 'ignorado')):
            matchear_movimiento(mov)
            mov.save(update_fields=['estado', 'sugerencia', 'sugerencia_motivo', 'actualizado_en'])
            n += 1
        messages.info(request, f'{n} movimiento(s) recalculado(s).')

    @admin.action(description='🚫 Ignorar (no corresponde a una reserva)')
    def ignorar(self, request, queryset):
        n = queryset.exclude(estado='aplicado').update(estado='ignorado')
        messages.info(request, f'{n} movimiento(s) ignorado(s).')

    # Los movimientos solo entran por el botón (API) y no se borran (auditables)
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
