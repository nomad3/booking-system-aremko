#!/usr/bin/env python
"""
Limpia comandas vacías que se crearon automáticamente por el bug
Uso: python limpiar_comandas_vacias.py
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Comanda

print("=" * 70)
print("LIMPIEZA DE COMANDAS VACÍAS")
print("=" * 70)
print()

# Buscar comandas vacías (sin items) en estado borrador
comandas_vacias = Comanda.objects.filter(
    estado='borrador',
    creada_por_cliente=True
).prefetch_related('detalles')

total = comandas_vacias.count()
print(f"Comandas en estado 'borrador' creadas por cliente: {total}")
print()

if total == 0:
    print("✅ No hay comandas vacías para limpiar")
    sys.exit(0)

# Filtrar las que realmente están vacías (sin items)
comandas_para_eliminar = []
for comanda in comandas_vacias:
    if comanda.detalles.count() == 0:
        comandas_para_eliminar.append(comanda)

print(f"Comandas completamente vacías (0 items): {len(comandas_para_eliminar)}")
print()

if len(comandas_para_eliminar) == 0:
    print("✅ Todas las comandas tienen items. No hay nada que limpiar.")
    sys.exit(0)

# Mostrar muestra
print("Muestra de comandas a eliminar:")
for comanda in comandas_para_eliminar[:10]:
    cliente = comanda.venta_reserva.cliente.nombre if comanda.venta_reserva else 'N/A'
    created = comanda.fecha_solicitud.strftime('%d/%m/%Y %H:%M') if hasattr(comanda, 'fecha_solicitud') and comanda.fecha_solicitud else 'N/A'
    print(f"   - Comanda #{comanda.id} | Cliente: {cliente} | Creada: {created}")

if len(comandas_para_eliminar) > 10:
    print(f"   ... y {len(comandas_para_eliminar) - 10} más")

print()
print("⚠️  ATENCIÓN: Esta acción NO se puede deshacer")
print()

# Pedir confirmación
respuesta = input(f"¿Eliminar {len(comandas_para_eliminar)} comandas vacías? (escribe 'SI' para confirmar): ")

if respuesta.strip().upper() != 'SI':
    print("❌ Operación cancelada. No se eliminó nada.")
    sys.exit(0)

print()
print("Eliminando...")

# Eliminar
ids_eliminados = [c.id for c in comandas_para_eliminar]
count, _ = Comanda.objects.filter(id__in=ids_eliminados).delete()

print(f"✅ {count} comandas eliminadas exitosamente")
print()

# Verificar
comandas_restantes = Comanda.objects.filter(
    estado='borrador',
    creada_por_cliente=True
).count()

print(f"Comandas en borrador restantes: {comandas_restantes}")
print()
print("=" * 70)
print("LIMPIEZA COMPLETADA")
print("=" * 70)
