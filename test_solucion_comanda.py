#!/usr/bin/env python
"""
Script para verificar que la solución de validación de inventario funciona
Ejecutar con: python manage.py shell < test_solucion_comanda.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.contrib.auth.models import User
from ventas.models import Producto

print("\n" + "=" * 80)
print("VERIFICACIÓN DE LA SOLUCIÓN DE COMANDAS")
print("=" * 80)
print()

print("1. PRODUCTOS DE PRUEBA DISPONIBLES:")
print("-" * 40)

# Mostrar productos con diferentes niveles de stock
productos_test = []

# Productos con buen stock
productos_ok = Producto.objects.filter(cantidad_disponible__gte=10).order_by('-cantidad_disponible')[:3]
for p in productos_ok:
    print(f"✅ {p.nombre}: {p.cantidad_disponible} unidades (STOCK OK)")
    productos_test.append(('ok', p))

# Productos con stock bajo
productos_bajo = Producto.objects.filter(cantidad_disponible__gt=0, cantidad_disponible__lt=5)[:3]
for p in productos_bajo:
    print(f"⚠️  {p.nombre}: {p.cantidad_disponible} unidades (STOCK BAJO)")
    productos_test.append(('bajo', p))

# Productos sin stock
productos_sin = Producto.objects.filter(cantidad_disponible=0)[:3]
for p in productos_sin:
    print(f"❌ {p.nombre}: {p.cantidad_disponible} unidades (SIN STOCK)")
    productos_test.append(('sin', p))

print("\n2. CASOS DE PRUEBA A REALIZAR:")
print("-" * 40)
print()
print("CASO 1: Comanda con todos los productos CON stock")
print("   → Debería GUARDARSE correctamente ✅")
print()
print("CASO 2: Comanda con al menos un producto SIN stock")
print("   → NO debería guardarse ❌")
print("   → Debe mostrar mensaje claro de qué productos faltan")
print()
print("CASO 3: Comanda con productos de stock bajo")
print("   → Debería GUARDARSE pero mostrar advertencia ⚠️")
print()

print("3. INSTRUCCIONES PARA PROBAR:")
print("-" * 40)
print()
print("1. Ve al admin de Django")
print("2. Entra a una VentaReserva en modo edición")
print("3. Haz clic en '➕ Agregar Comanda con Productos'")
print("4. En el popup, prueba agregar:")
print()
print("   PRUEBA 1 - Solo productos con stock OK:")

if productos_ok:
    for p in productos_ok[:2]:
        print(f"   • {p.nombre} - Cantidad: 1")

print()
print("   PRUEBA 2 - Incluir un producto SIN stock:")

if productos_ok and productos_sin:
    print(f"   • {productos_ok[0].nombre} - Cantidad: 1")
    print(f"   • {productos_sin[0].nombre} - Cantidad: 1 (SIN STOCK)")

print()
print("   PRUEBA 3 - Producto con stock bajo:")

if productos_bajo:
    print(f"   • {productos_bajo[0].nombre} - Cantidad: {productos_bajo[0].cantidad_disponible}")

print()
print("4. COMPORTAMIENTO ESPERADO:")
print("-" * 40)
print()
print("✅ Si TODOS tienen stock → Se guarda y muestra mensaje de éxito")
print("❌ Si ALGUNO no tiene stock → NO se guarda y muestra:")
print("   - Qué productos faltan")
print("   - Cuánto stock hay disponible")
print("   - Cuánto falta")
print("⚠️  Si hay stock bajo → Se guarda pero advierte")
print()
print("=" * 80)
print("La solución está ACTIVA - Prueba ahora en el admin")
print("=" * 80)