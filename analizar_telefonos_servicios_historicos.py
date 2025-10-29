"""
Script para analizar números de teléfono de clientes con servicios históricos
Identifica teléfonos extranjeros y con formatos incorrectos
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente, ServiceHistory
from collections import defaultdict

print("\n" + "="*100)
print("ANALISIS DE TELEFONOS EN SERVICIOS HISTORICOS")
print("="*100 + "\n")

# Obtener todos los clientes únicos que tienen servicios históricos
clientes_con_servicios = Cliente.objects.filter(
    historial_servicios__isnull=False
).distinct()

total_clientes = clientes_con_servicios.count()
print(f"Total de clientes con servicios históricos: {total_clientes:,}\n")

# Categorizar por formato de teléfono
categorias = {
    'chilenos_correctos': [],      # +56XXXXXXXXX (11-12 dígitos)
    'chilenos_sin_mas': [],         # 56XXXXXXXXX (sin +)
    'argentinos': [],               # +549, +54, 549, 54
    'otros_extranjeros': [],        # +1, +52, +55, etc
    'sin_telefono': [],             # None o vacío
    'formato_raro': []              # Otros formatos extraños
}

for cliente in clientes_con_servicios:
    telefono = cliente.telefono

    # Contar servicios del cliente
    num_servicios = ServiceHistory.objects.filter(cliente=cliente).count()

    info = {
        'id': cliente.id,
        'nombre': cliente.nombre,
        'telefono': telefono,
        'email': cliente.email or 'sin email',
        'num_servicios': num_servicios
    }

    if not telefono or telefono.strip() == '':
        categorias['sin_telefono'].append(info)
    elif telefono.startswith('+56'):
        if len(telefono) in [12, 13]:  # +56 + 9 o 10 dígitos
            categorias['chilenos_correctos'].append(info)
        else:
            categorias['formato_raro'].append(info)
    elif telefono.startswith('56') and not telefono.startswith('+'):
        if len(telefono) in [11, 12]:
            categorias['chilenos_sin_mas'].append(info)
        else:
            categorias['formato_raro'].append(info)
    elif telefono.startswith('+549') or telefono.startswith('549') or telefono.startswith('+54') or telefono.startswith('54'):
        categorias['argentinos'].append(info)
    elif telefono.startswith('+'):
        # Otros países con +
        categorias['otros_extranjeros'].append(info)
    else:
        categorias['formato_raro'].append(info)

# MOSTRAR RESULTADOS
print("="*100)
print("RESUMEN POR CATEGORIA")
print("="*100 + "\n")

print(f"✅ Chilenos formato correcto (+56...):  {len(categorias['chilenos_correctos']):>6,}")
print(f"⚠️  Chilenos sin + (56...):              {len(categorias['chilenos_sin_mas']):>6,}")
print(f"🇦🇷 Argentinos (+549, 549, +54, 54):     {len(categorias['argentinos']):>6,}")
print(f"🌎 Otros extranjeros (+1, +52, etc):     {len(categorias['otros_extranjeros']):>6,}")
print(f"❌ Sin teléfono:                        {len(categorias['sin_telefono']):>6,}")
print(f"❓ Formato raro:                        {len(categorias['formato_raro']):>6,}")
print(f"{'-'*100}")
print(f"   TOTAL:                               {total_clientes:>6,}")

# DETALLE DE EXTRANJEROS
if categorias['argentinos']:
    print("\n" + "="*100)
    print("🇦🇷 DETALLE: CLIENTES ARGENTINOS")
    print("="*100)
    for i, info in enumerate(categorias['argentinos'], 1):
        print(f"\n{i}. ID: {info['id']} - {info['nombre']}")
        print(f"   Telefono: {info['telefono']}")
        print(f"   Email: {info['email']}")
        print(f"   Servicios históricos: {info['num_servicios']}")

if categorias['otros_extranjeros']:
    print("\n" + "="*100)
    print("🌎 DETALLE: CLIENTES OTROS PAISES")
    print("="*100)
    for i, info in enumerate(categorias['otros_extranjeros'], 1):
        print(f"\n{i}. ID: {info['id']} - {info['nombre']}")
        print(f"   Telefono: {info['telefono']}")
        print(f"   Email: {info['email']}")
        print(f"   Servicios históricos: {info['num_servicios']}")

if categorias['chilenos_sin_mas']:
    print("\n" + "="*100)
    print("⚠️  DETALLE: CHILENOS SIN + (CORREGIBLE)")
    print("="*100)
    print(f"Total: {len(categorias['chilenos_sin_mas'])} clientes")
    # Mostrar solo los primeros 10
    for i, info in enumerate(categorias['chilenos_sin_mas'][:10], 1):
        print(f"{i}. ID {info['id']}: {info['telefono']} → +{info['telefono']}")
    if len(categorias['chilenos_sin_mas']) > 10:
        print(f"... y {len(categorias['chilenos_sin_mas']) - 10} más")

if categorias['formato_raro']:
    print("\n" + "="*100)
    print("❓ DETALLE: FORMATOS RAROS")
    print("="*100)
    for i, info in enumerate(categorias['formato_raro'], 1):
        print(f"\n{i}. ID: {info['id']} - {info['nombre']}")
        print(f"   Telefono: {info['telefono']}")
        print(f"   Email: {info['email']}")
        print(f"   Servicios históricos: {info['num_servicios']}")

# RECOMENDACIONES
print("\n" + "="*100)
print("RECOMENDACIONES")
print("="*100)

extranjeros_total = len(categorias['argentinos']) + len(categorias['otros_extranjeros'])
if extranjeros_total > 0:
    print(f"\n1. ELIMINAR {extranjeros_total} CLIENTES EXTRANJEROS:")
    print(f"   - {len(categorias['argentinos'])} argentinos")
    print(f"   - {len(categorias['otros_extranjeros'])} de otros países")
    print(f"   - Esto eliminará también sus {sum(c['num_servicios'] for c in categorias['argentinos'] + categorias['otros_extranjeros'])} servicios históricos")

if categorias['chilenos_sin_mas']:
    print(f"\n2. NORMALIZAR {len(categorias['chilenos_sin_mas'])} TELEFONOS CHILENOS:")
    print(f"   - Agregar '+' al inicio (56... → +56...)")
    print(f"   - Esto NO elimina datos, solo corrige formato")

if categorias['formato_raro']:
    print(f"\n3. REVISAR {len(categorias['formato_raro'])} FORMATOS RAROS:")
    print(f"   - Decidir caso por caso si son chilenos mal formateados o extranjeros")

print("\n" + "="*100)
print("PROXIMOS PASOS:")
print("="*100)
print("1. Revisar el detalle de extranjeros arriba")
print("2. Confirmar que quieres eliminarlos")
print("3. Ejecutar script de limpieza (crear si confirmas)")
print("\n" + "="*100 + "\n")
