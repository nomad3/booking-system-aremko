#!/usr/bin/env python
"""
FIX TEMPORAL - Comentar ComandaInline para restaurar el admin

INSTRUCCIONES URGENTES:

1. En ventas/admin.py, buscar la línea (aproximadamente 354):
   inlines = [ReservaServicioInline, ReservaProductoInline, GiftCardInline, PagoInline, ComandaInline]

2. CAMBIAR A:
   inlines = [ReservaServicioInline, ReservaProductoInline, GiftCardInline, PagoInline]  # , ComandaInline]

3. Esto deshabilitará temporalmente las comandas en VentaReserva pero restaurará el admin.

ALTERNATIVA - Si eso no funciona:

En ventas/admin.py, buscar ComandaInline (línea ~253) y cambiar:

DE:
    fields = ('id', 'estado', 'fecha_solicitud')
    readonly_fields = ('id', 'estado', 'fecha_solicitud')

A:
    fields = ('id',)
    readonly_fields = ('id',)

Esto simplifica aún más el inline.
"""

print(__doc__)