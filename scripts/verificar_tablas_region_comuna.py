"""
Script para verificar el estado de las tablas Region y Comuna en la base de datos.

USO:
    python manage.py shell < scripts/verificar_tablas_region_comuna.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

print("\n" + "="*100)
print("VERIFICACIÓN DE TABLAS Y COLUMNAS - REGIÓN Y COMUNA")
print("="*100 + "\n")

cursor = connection.cursor()

# 1. Verificar tabla Region
print("1️⃣  Verificando tabla ventas_region...")
cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'ventas_region'
    );
""")
region_exists = cursor.fetchone()[0]
print(f"   ✓ Tabla ventas_region existe: {region_exists}")

# 2. Verificar tabla Comuna
print("\n2️⃣  Verificando tabla ventas_comuna...")
cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'ventas_comuna'
    );
""")
comuna_exists = cursor.fetchone()[0]
print(f"   ✓ Tabla ventas_comuna existe: {comuna_exists}")

# 3. Verificar tabla ClientePremio (que causó el error)
print("\n3️⃣  Verificando tabla ventas_clientepremio...")
cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'ventas_clientepremio'
    );
""")
clientepremio_exists = cursor.fetchone()[0]
print(f"   ✓ Tabla ventas_clientepremio existe: {clientepremio_exists}")

# 4. Verificar tabla ServiceHistory (que también se intenta crear)
print("\n4️⃣  Verificando tabla crm_service_history...")
cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'crm_service_history'
    );
""")
servicehistory_exists = cursor.fetchone()[0]
print(f"   ✓ Tabla crm_service_history existe: {servicehistory_exists}")

# 5. Verificar tabla Premio
print("\n5️⃣  Verificando tabla ventas_premio...")
cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'ventas_premio'
    );
""")
premio_exists = cursor.fetchone()[0]
print(f"   ✓ Tabla ventas_premio existe: {premio_exists}")

# 6. Verificar tabla HistorialTramo
print("\n6️⃣  Verificando tabla ventas_historialtramo...")
cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'ventas_historialtramo'
    );
""")
historialtramo_exists = cursor.fetchone()[0]
print(f"   ✓ Tabla ventas_historialtramo existe: {historialtramo_exists}")

# 7. Verificar columnas region_id y comuna_id en Cliente
print("\n7️⃣  Verificando columnas en ventas_cliente...")
cursor.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'ventas_cliente'
    AND column_name IN ('region_id', 'comuna_id');
""")
columnas = [row[0] for row in cursor.fetchall()]
if columnas:
    print(f"   ✓ Columnas encontradas: {', '.join(columnas)}")
else:
    print(f"   ✗ Columnas region_id/comuna_id NO EXISTEN en ventas_cliente")

print("\n" + "="*100)
print("RESUMEN")
print("="*100)

# Tablas que YA EXISTEN (y causan el error)
tablas_existentes = []
if clientepremio_exists:
    tablas_existentes.append("ventas_clientepremio")
if servicehistory_exists:
    tablas_existentes.append("crm_service_history")
if premio_exists:
    tablas_existentes.append("ventas_premio")
if historialtramo_exists:
    tablas_existentes.append("ventas_historialtramo")

# Tablas que NECESITAMOS crear
tablas_faltantes = []
if not region_exists:
    tablas_faltantes.append("ventas_region")
if not comuna_exists:
    tablas_faltantes.append("ventas_comuna")

# Columnas que NECESITAMOS crear
columnas_faltantes = []
if 'region_id' not in columnas:
    columnas_faltantes.append("region_id en ventas_cliente")
if 'comuna_id' not in columnas:
    columnas_faltantes.append("comuna_id en ventas_cliente")

print("\n📊 DIAGNÓSTICO:")
print(f"\n✅ Tablas que YA EXISTEN (causan error en migración):")
if tablas_existentes:
    for tabla in tablas_existentes:
        print(f"   • {tabla}")
else:
    print("   • Ninguna")

print(f"\n❌ Tablas que FALTAN crear:")
if tablas_faltantes:
    for tabla in tablas_faltantes:
        print(f"   • {tabla}")
else:
    print("   • Ninguna (todas las tablas necesarias ya existen)")

print(f"\n❌ Columnas que FALTAN crear:")
if columnas_faltantes:
    for columna in columnas_faltantes:
        print(f"   • {columna}")
else:
    print("   • Ninguna (todas las columnas necesarias ya existen)")

print("\n" + "="*100)
print("SOLUCIÓN RECOMENDADA")
print("="*100)

if tablas_existentes and (tablas_faltantes or columnas_faltantes):
    print("""
La migración 0057 intenta crear tablas que YA EXISTEN, pero también necesita
crear tablas/columnas que FALTAN.

OPCIÓN 1 (RECOMENDADA): Editar la migración manualmente
    1. Editar ventas/migrations/0057_*.py
    2. Comentar/eliminar operaciones de tablas que ya existen
    3. Dejar solo operaciones de Region, Comuna y columnas en Cliente
    4. Ejecutar: python manage.py migrate ventas

OPCIÓN 2: Migración SQL manual
    1. Crear tablas Region y Comuna manualmente con SQL
    2. Agregar columnas region_id y comuna_id a ventas_cliente con SQL
    3. Marcar migración como fake: python manage.py migrate ventas 0057 --fake
    """)
elif not tablas_faltantes and not columnas_faltantes:
    print("""
✅ ¡BUENAS NOTICIAS!

Todas las tablas y columnas necesarias YA EXISTEN en la base de datos.

SOLUCIÓN:
    python manage.py migrate ventas 0057 --fake

Esto marca la migración como aplicada sin ejecutarla.
Luego puedes continuar con:
    python manage.py loaddata regiones_comunas_chile
    """)
else:
    print("""
Necesitas crear las tablas/columnas faltantes.

Si la migración 0057 tiene conflictos, considera crear una migración
manual con SQL.
    """)

print("\n" + "="*100 + "\n")
