"""Admin de solo-lectura para auditar las conciliaciones aplicadas (AP-001)."""

from django.contrib import admin

from .models import ReconciliacionLog


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
