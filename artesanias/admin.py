# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import ArtesaniaPieza


@admin.register(ArtesaniaPieza)
class ArtesaniaPiezaAdmin(admin.ModelAdmin):
    """Correcciones finas del catálogo (el día a día ocurre en /artesanias/)."""

    list_display = ('codigo', 'nombre', 'precio_fmt', 'estado', 'venta_reserva',
                    'venta_monto', 'venta_fecha')
    list_filter = ('estado',)
    search_fields = ('codigo', 'nombre', 'notas')
    list_editable = ('estado',)
    readonly_fields = ('creado_en', 'actualizado_en')
    autocomplete_fields = ()
    raw_id_fields = ('venta_reserva',)

    @admin.display(description='Precio', ordering='precio')
    def precio_fmt(self, obj):
        return f'${int(obj.precio):,}'.replace(',', '.')
