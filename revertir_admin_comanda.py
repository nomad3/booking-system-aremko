#!/usr/bin/env python
"""
Script para REVERTIR el cambio en admin.py y aplicar una versión más segura
"""

print("""
================================================================================
REVERSIÓN DE EMERGENCIA - COMANDAS ADMIN
================================================================================

PROBLEMA IDENTIFICADO:
- El método validar_stock_completo intenta acceder a formset.cleaned_data
- Esto puede no estar disponible en ciertos contextos del admin
- Causa Error 500 al guardar y al abrir reservas con comandas

SOLUCIÓN: Revertir a una versión más simple y segura

CÓDIGO A REEMPLAZAR EN ventas/admin.py:

Busca el método save_formset en ComandaAdmin y REEMPLÁZALO COMPLETO con:

def save_formset(self, request, form, formset, change):
    '''Guardar el formset con validación básica de inventario'''
    try:
        instances = formset.save(commit=False)

        # Validación simple: verificar stock antes de guardar
        productos_sin_stock = []

        for instance in instances:
            if hasattr(instance, 'producto') and hasattr(instance, 'cantidad'):
                if instance.producto and instance.cantidad:
                    if instance.producto.cantidad_disponible < instance.cantidad:
                        productos_sin_stock.append(
                            f"{instance.producto.nombre}: Solicitado {instance.cantidad}, "
                            f"Disponible {instance.producto.cantidad_disponible}"
                        )

        # Si hay productos sin stock, mostrar advertencia pero PERMITIR guardar
        # (para no bloquear el sistema)
        if productos_sin_stock:
            from django.contrib import messages
            messages.warning(
                request,
                f"⚠️ ADVERTENCIA: Los siguientes productos tienen inventario insuficiente:"
            )
            for msg in productos_sin_stock:
                messages.warning(request, f"• {msg}")
            messages.info(
                request,
                "La comanda se guardó pero el inventario no se actualizó para productos sin stock."
            )

        # Guardar las instancias del formset (DetalleComanda)
        for instance in instances:
            instance.save()

        # Eliminar instancias marcadas para borrar
        for obj in formset.deleted_objects:
            obj.delete()

        formset.save_m2m()

        # Si es una nueva comanda creada desde admin, crear ReservaProducto
        comanda = form.instance
        if hasattr(comanda, '_is_new_from_admin') and comanda._is_new_from_admin and comanda.venta_reserva:
            from django.utils import timezone
            from .models import ReservaProducto

            for detalle in comanda.detalles.all():
                # Solo crear ReservaProducto si hay stock suficiente
                if detalle.producto.cantidad_disponible >= detalle.cantidad:
                    fecha_entrega_reserva = (
                        comanda.fecha_entrega_objetivo.date()
                        if comanda.fecha_entrega_objetivo
                        else timezone.now().date()
                    )

                    try:
                        ReservaProducto.objects.get_or_create(
                            venta_reserva=comanda.venta_reserva,
                            producto=detalle.producto,
                            defaults={
                                'cantidad': detalle.cantidad,
                                'precio_unitario_venta': detalle.precio_unitario,
                                'fecha_entrega': fecha_entrega_reserva
                            }
                        )
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Error creando ReservaProducto: {e}")

        # Mensaje de éxito
        from django.contrib import messages
        if comanda.pk:
            messages.success(
                request,
                f"✅ Comanda #{comanda.id} guardada correctamente"
            )

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error en save_formset de ComandaAdmin: {str(e)}", exc_info=True)
        raise

IMPORTANTE: También ELIMINA el método validar_stock_completo que agregamos antes.

================================================================================
PASOS URGENTES:
================================================================================

1. Edita ventas/admin.py
2. Elimina el método validar_stock_completo
3. Reemplaza save_formset con el código de arriba
4. Guarda y espera el deploy

Esta versión:
- NO bloquea el guardado (evita Error 500)
- Muestra advertencias de stock bajo
- Solo crea ReservaProducto si hay stock
- Es más segura y estable

================================================================================
""")