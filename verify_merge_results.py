"""
Script para verificar que la fusión fue exitosa
Verifica que no haya duplicados y que los datos estén consolidados
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente, VentaReserva, ServiceHistory
from collections import defaultdict

print("\n" + "="*80)
print("🔍 VERIFICACIÓN POST-FUSIÓN")
print("="*80 + "\n")

# 1. Verificar que no haya duplicados de teléfono
print("1. VERIFICANDO DUPLICADOS DE TELÉFONO...")
all_clients = Cliente.objects.all()
phone_groups = defaultdict(list)

for cliente in all_clients:
    if cliente.telefono:
        normalized = cliente.telefono.replace('+', '').strip()
        if normalized:
            phone_groups[normalized].append(cliente)

duplicates = [(phone, clients) for phone, clients in phone_groups.items() if len(clients) > 1]

if duplicates:
    print(f"   ⚠️  AÚN HAY {len(duplicates)} GRUPOS DE DUPLICADOS")
    for phone, clients in duplicates[:5]:
        print(f"      {phone}: {len(clients)} clientes")
        for c in clients:
            ventas = VentaReserva.objects.filter(cliente=c).count()
            historicos = ServiceHistory.objects.filter(cliente=c).count()
            print(f"         [{c.id}] {c.nombre[:40]} - Ventas: {ventas}, Históricos: {historicos}")
else:
    print("   ✅ NO HAY DUPLICADOS DE TELÉFONO")

print()

# 2. Verificar clasificación de clientes
print("2. CLASIFICACIÓN DE CLIENTES...")
current_clients = 0
historical_only = 0
empty_clients = 0

for cliente in all_clients:
    has_ventas = VentaReserva.objects.filter(cliente=cliente).exists()
    has_historicos = ServiceHistory.objects.filter(cliente=cliente).exists()

    if has_ventas:
        current_clients += 1
    elif has_historicos:
        historical_only += 1
    else:
        empty_clients += 1

print(f"   👑 Clientes ACTUALES (con VentaReserva): {current_clients}")
print(f"   📋 Clientes HISTÓRICOS (solo ServiceHistory): {historical_only}")
print(f"   ⚪ Clientes VACÍOS: {empty_clients}")
print()

# 3. Verificar casos específicos que vimos antes
print("3. VERIFICANDO CASOS ESPECÍFICOS...")
test_cases = [
    ('56975544661', 'Marjorie Melo'),
    ('56962801057', 'Valentina'),
    ('56981315333', 'Mauricio'),
]

for phone, expected_name in test_cases:
    clients = Cliente.objects.filter(telefono__contains=phone)
    print(f"   📞 {phone} ({expected_name}):")
    if clients.count() == 0:
        print(f"      ❌ No encontrado")
    elif clients.count() == 1:
        c = clients.first()
        ventas = VentaReserva.objects.filter(cliente=c).count()
        historicos = ServiceHistory.objects.filter(cliente=c).count()
        print(f"      ✅ 1 cliente: [{c.id}] {c.nombre}")
        print(f"         Servicios: {ventas} actuales + {historicos} históricos = {ventas + historicos} total")
    else:
        print(f"      ⚠️  {clients.count()} clientes (AÚN DUPLICADO)")

print()

# 4. Estadísticas generales
print("4. ESTADÍSTICAS GENERALES...")
total_clientes = Cliente.objects.count()
total_ventas = VentaReserva.objects.count()
total_historicos = ServiceHistory.objects.count()

print(f"   Total clientes: {total_clientes}")
print(f"   Total VentaReserva: {total_ventas}")
print(f"   Total ServiceHistory: {total_historicos}")

print("\n" + "="*80)
print("✅ VERIFICACIÓN COMPLETADA")
print("="*80 + "\n")
