#!/usr/bin/env python
"""
Diagnóstico FINAL del problema de comandas
Ejecutar con: python manage.py shell < diagnostico_comandas_final.py
"""
import os
import sys
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import transaction
from ventas.models import Comanda, DetalleComanda, VentaReserva, ReservaProducto, Producto
from django.utils import timezone
from django.contrib.auth import get_user_model

print("\n" + "=" * 80)
print("DIAGNÓSTICO FINAL - PROBLEMA DE COMANDAS E INVENTARIO")
print("=" * 80)

# 1. PROBLEMA IDENTIFICADO
print("\n1. PROBLEMA IDENTIFICADO")
print("-" * 40)
print("✓ El signal 'actualizar_inventario' en ventas/signals/main_signals.py")
print("✓ Se ejecuta cuando se guarda un ReservaProducto")
print("✓ Llama a producto.reducir_inventario(cantidad)")
print("✓ Si no hay suficiente stock, lanza ValueError('No hay suficiente inventario disponible.')")
print("✓ Esto causa Error 500 al guardar comandas con productos sin stock")

# 2. Verificar productos y su inventario REAL
print("\n2. INVENTARIO ACTUAL DE PRODUCTOS")
print("-" * 40)

productos = Producto.objects.filter(publicado_web=True).order_by('cantidad_disponible')[:10]
print(f"Productos con menor inventario (usando campo correcto 'cantidad_disponible'):")
for prod in productos:
    print(f"  - {prod.nombre}: Stock={prod.cantidad_disponible}, Precio=${prod.precio_base}")

sin_stock = Producto.objects.filter(cantidad_disponible=0, publicado_web=True).count()
print(f"\nProductos publicados SIN STOCK: {sin_stock}")

# 3. Probar el comportamiento actual
print("\n3. PRUEBA DE COMPORTAMIENTO ACTUAL")
print("-" * 40)

# Buscar productos para prueba
producto_con_stock = Producto.objects.filter(
    publicado_web=True,
    cantidad_disponible__gt=5
).first()

producto_sin_stock = Producto.objects.filter(
    publicado_web=True,
    cantidad_disponible=0
).first()

if producto_con_stock:
    print(f"\nProducto CON stock: {producto_con_stock.nombre}")
    print(f"  Stock disponible: {producto_con_stock.cantidad_disponible}")

if producto_sin_stock:
    print(f"\nProducto SIN stock: {producto_sin_stock.nombre}")
    print(f"  Stock disponible: {producto_sin_stock.cantidad_disponible}")

# 4. Simular el error
print("\n4. SIMULACIÓN DEL ERROR")
print("-" * 40)

if producto_sin_stock:
    print(f"\nSimulando crear ReservaProducto con producto sin stock...")
    print(f"Producto: {producto_sin_stock.nombre} (stock: {producto_sin_stock.cantidad_disponible})")

    try:
        # Esto debería fallar
        producto_sin_stock.reducir_inventario(1)
        print("✗ ERROR: No debería haber funcionado!")
    except ValueError as e:
        print(f"✓ Error esperado: {e}")
        print("  Este es el error que causa el problema en el admin")

# 5. Estado actual del admin
print("\n5. ESTADO ACTUAL DEL ADMIN")
print("-" * 40)

try:
    from ventas.admin import VentaReservaAdmin
    inlines = getattr(VentaReservaAdmin, 'inlines', [])
    inline_names = [inline.__name__ for inline in inlines]

    if 'ComandaInline' in inline_names:
        print("⚠ ComandaInline ESTÁ habilitado - puede causar errores")
    else:
        print("✓ ComandaInline está deshabilitado - admin protegido")

    print(f"\nInlines activos: {', '.join(inline_names)}")
except Exception as e:
    print(f"✗ Error verificando admin: {e}")

# 6. Verificar comandas recientes
print("\n6. COMANDAS RECIENTES")
print("-" * 40)

comandas_hoy = Comanda.objects.filter(
    fecha_solicitud__date=timezone.now().date()
).order_by('-fecha_solicitud')[:5]

if comandas_hoy:
    print(f"Comandas de hoy: {comandas_hoy.count()}")
    for comanda in comandas_hoy:
        detalles = comanda.detalles.count()
        print(f"  - Comanda #{comanda.id}: {detalles} productos, estado={comanda.estado}")
else:
    print("No hay comandas de hoy")

# 7. SOLUCIÓN PROPUESTA
print("\n" + "=" * 80)
print("SOLUCIÓN PROPUESTA")
print("=" * 80)

print("\nOPCIÓN 1 - VALIDACIÓN PREVENTIVA (Recomendada):")
print("-" * 40)
print("""
En ventas/admin.py, método save_formset de ComandaAdmin:

def save_formset(self, request, form, formset, change):
    instances = formset.save(commit=False)

    # Validar stock ANTES de guardar
    errores = []
    for obj in instances:
        if isinstance(obj, ReservaProducto) and obj.producto:
            if obj.producto.cantidad_disponible < obj.cantidad:
                errores.append(f"{obj.producto.nombre}: solo hay {obj.producto.cantidad_disponible} unidades")

    if errores:
        # Mostrar advertencias pero NO detener el proceso
        for error in errores:
            messages.warning(request, f"Sin stock: {error}")
        # Filtrar productos sin stock
        instances = [obj for obj in instances
                    if not (isinstance(obj, ReservaProducto) and
                           obj.producto and
                           obj.producto.cantidad_disponible < obj.cantidad)]

    # Guardar solo los que tienen stock
    for obj in instances:
        obj.save()

    formset.save_m2m()
""")

print("\nOPCIÓN 2 - MODIFICAR EL SIGNAL:")
print("-" * 40)
print("""
En ventas/signals/main_signals.py, modificar actualizar_inventario:

@receiver(post_save, sender=ReservaProducto)
def actualizar_inventario(sender, instance, created, **kwargs):
    try:
        if created and instance.producto:
            # En lugar de lanzar excepción, solo loggear
            if instance.producto.cantidad_disponible < instance.cantidad:
                logger.warning(f"Sin stock para {instance.producto.nombre}")
                # Opcional: marcar la reserva de alguna forma
            else:
                instance.producto.reducir_inventario(instance.cantidad)
    except Exception as e:
        logger.error(f"Error en actualizar_inventario: {e}")
        # NO re-lanzar la excepción
""")

print("\nOPCIÓN 3 - DESACTIVAR TEMPORALMENTE:")
print("-" * 40)
print("""
Como medida temporal mientras se implementa la solución:

from django.db.models.signals import post_save
from ventas.signals.main_signals import actualizar_inventario

# Desconectar el signal
post_save.disconnect(actualizar_inventario, sender=ReservaProducto)
""")

print("\nRECOMENDACIÓN FINAL:")
print("-" * 40)
print("1. Implementar OPCIÓN 1 para validación en el admin")
print("2. Re-habilitar ComandaInline cuando esté listo")
print("3. Considerar agregar campo 'validado_stock' en ReservaProducto")
print("4. Implementar vista de 'Productos sin stock' para cafetería")

print("\n" + "=" * 80)