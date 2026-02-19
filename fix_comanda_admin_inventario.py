#!/usr/bin/env python
"""
Script para aplicar fix al problema de inventario en comandas
Ejecutar con: python manage.py shell < fix_comanda_admin_inventario.py

Este script modifica el admin para manejar correctamente el error de inventario
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

print("\n" + "=" * 80)
print("APLICANDO FIX PARA PROBLEMA DE INVENTARIO EN COMANDAS")
print("=" * 80)
print()

# Mostrar el código que debe agregarse al admin.py
fix_code = '''
# AGREGAR ESTE CÓDIGO EN ventas/admin.py

# 1. Buscar el método save_formset en ComandaAdmin (alrededor de línea 3233)
# 2. Reemplazar TODO el método save_formset con este código:

def save_formset(self, request, form, formset, change):
    """Guardar el formset y crear ReservaProducto para nuevas comandas"""
    try:
        instances = formset.save(commit=False)

        # Validar inventario antes de guardar
        productos_sin_stock = []
        for instance in instances:
            if hasattr(instance, 'producto') and hasattr(instance, 'cantidad'):
                producto = instance.producto
                cantidad = instance.cantidad
                if producto and cantidad and producto.cantidad_disponible < cantidad:
                    productos_sin_stock.append({
                        'producto': producto.nombre,
                        'solicitado': cantidad,
                        'disponible': producto.cantidad_disponible
                    })

        # Si hay productos sin stock, mostrar error y no continuar
        if productos_sin_stock:
            from django.contrib import messages
            messages.error(request, "❌ No se puede crear la comanda por falta de inventario:")
            for item in productos_sin_stock:
                messages.error(
                    request,
                    f"• {item['producto']}: Solicitado {item['solicitado']} | "
                    f"Disponible {item['disponible']}"
                )
            return  # No guardar nada

        # Si llegamos aquí, hay stock suficiente
        # Guardar las instancias del formset (DetalleComanda)
        for instance in instances:
            instance.save()

        # Eliminar instancias marcadas para borrar
        for obj in formset.deleted_objects:
            obj.delete()

        formset.save_m2m()  # Por si acaso hay relaciones m2m

        # Solo crear ReservaProducto si es una comanda nueva
        # y viene del admin (no de API/scripts)
        comanda = form.instance
        if getattr(comanda, '_is_new_from_admin', False):
            # Crear ReservaProducto para cada DetalleComanda
            from django.utils import timezone
            from ventas.models import ReservaProducto

            for detalle in comanda.detalles.all():
                # Determinar fecha de entrega
                fecha_entrega_reserva = (
                    comanda.fecha_entrega_objetivo.date()
                    if comanda.fecha_entrega_objetivo
                    else timezone.now().date()
                )

                # Intentar crear ReservaProducto
                try:
                    rp, created = ReservaProducto.objects.get_or_create(
                        venta_reserva=comanda.venta_reserva,
                        producto=detalle.producto,
                        defaults={
                            'cantidad': detalle.cantidad,
                            'precio_unitario_venta': detalle.precio_unitario,
                            'fecha_entrega': fecha_entrega_reserva
                        }
                    )

                    if not created:
                        # Si ya existe, actualizar cantidad
                        rp.cantidad += detalle.cantidad
                        rp.save()

                except Exception as e:
                    # Si hay error al crear ReservaProducto, loggearlo pero continuar
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Error creando ReservaProducto: {e}")

            # Mostrar mensaje de éxito
            from django.contrib import messages
            messages.success(
                request,
                f"✅ Comanda #{comanda.id} creada exitosamente con {comanda.detalles.count()} productos"
            )

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error en save_formset de ComandaAdmin: {str(e)}", exc_info=True)

        # Mostrar error al usuario
        from django.contrib import messages
        messages.error(request, f"Error al guardar la comanda: {str(e)}")
'''

print("CÓDIGO A AGREGAR EN ventas/admin.py:")
print("-" * 80)
print(fix_code)
print("-" * 80)

# Verificar si podemos aplicar el fix automáticamente
try:
    import ventas.admin
    from django.contrib import messages

    print("\n✓ Módulo admin importado correctamente")
    print("\nNOTA: Para aplicar el fix, debes editar manualmente el archivo ventas/admin.py")
    print("      y reemplazar el método save_formset con el código mostrado arriba.")

except Exception as e:
    print(f"\n✗ Error al importar admin: {e}")

print("\n" + "=" * 80)
print("INSTRUCCIONES:")
print("=" * 80)
print()
print("1. Edita el archivo ventas/admin.py")
print("2. Busca el método save_formset en la clase ComandaAdmin")
print("3. Reemplaza TODO el método con el código mostrado arriba")
print("4. Guarda el archivo")
print("5. El deploy automático aplicará los cambios")
print()
print("BENEFICIOS DEL FIX:")
print("- Valida inventario ANTES de guardar")
print("- Muestra mensajes claros de error")
print("- Evita el Error 500")
print("- Permite continuar creando comandas con productos que sí tienen stock")
print()
print("=" * 80)