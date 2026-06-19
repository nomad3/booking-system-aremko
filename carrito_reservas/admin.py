from django.contrib import admin
from .models import CarritoReserva


@admin.register(CarritoReserva)
class CarritoReservaAdmin(admin.ModelAdmin):
    list_display = ('canal', 'external_id', 'estado', 'contar_items', 'total', 'created_at')
    list_filter = ('canal', 'estado', 'created_at')
    search_fields = ('external_id',)
    readonly_fields = (
        'canal', 'external_id', 'items', 'subtotal_servicios', 'subtotal_productos',
        'descuento_combo', 'packs_aplicados', 'total', 'created_at', 'updated_at'
    )

    fieldsets = (
        ('Conversación', {
            'fields': ('canal', 'external_id')
        }),
        ('Items', {
            'fields': ('items', 'contar_items')
        }),
        ('Totales', {
            'fields': ('subtotal_servicios', 'subtotal_productos', 'descuento_combo', 'total')
        }),
        ('Descuentos aplicados', {
            'fields': ('packs_aplicados',)
        }),
        ('Estado', {
            'fields': ('estado', 'venta_reserva')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'expires_at')
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
