"""
SCRIPT SQL MANUAL: Crear tablas Region y Comuna

Este script crea las tablas y columnas necesarias usando SQL directo,
evitando el conflicto con la migración 0057 que intenta crear tablas existentes.

EJECUTA:
1. Este script para crear tablas/columnas
2. python manage.py migrate ventas 0057 --fake (para marcar migración como aplicada)
3. python manage.py loaddata regiones_comunas_chile (para cargar datos)
4. python manage.py shell < scripts/migrar_clientes_a_region_comuna.py (para migrar datos)

USO:
    python manage.py shell < scripts/crear_tablas_region_comuna.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

print("\n" + "="*100)
print("CREACIÓN MANUAL DE TABLAS REGION Y COMUNA")
print("="*100 + "\n")

cursor = connection.cursor()

# ============================================
# 1. CREAR TABLA VENTAS_REGION
# ============================================
print("1️⃣  Creando tabla ventas_region...")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS ventas_region (
        id SERIAL PRIMARY KEY,
        codigo VARCHAR(10) UNIQUE NOT NULL,
        nombre VARCHAR(100) NOT NULL,
        orden INTEGER NOT NULL DEFAULT 0
    );
""")

print("   ✓ Tabla ventas_region creada")

# ============================================
# 2. CREAR TABLA VENTAS_COMUNA
# ============================================
print("\n2️⃣  Creando tabla ventas_comuna...")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS ventas_comuna (
        id SERIAL PRIMARY KEY,
        region_id INTEGER NOT NULL REFERENCES ventas_region(id) ON DELETE CASCADE,
        nombre VARCHAR(100) NOT NULL,
        codigo VARCHAR(10),
        UNIQUE (region_id, nombre)
    );
""")

print("   ✓ Tabla ventas_comuna creada")

# ============================================
# 3. AGREGAR COLUMNAS A VENTAS_CLIENTE
# ============================================
print("\n3️⃣  Agregando columnas region_id y comuna_id a ventas_cliente...")

# Verificar si las columnas ya existen
cursor.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'ventas_cliente'
    AND column_name IN ('region_id', 'comuna_id');
""")
columnas_existentes = [row[0] for row in cursor.fetchall()]

if 'region_id' not in columnas_existentes:
    cursor.execute("""
        ALTER TABLE ventas_cliente
        ADD COLUMN region_id INTEGER NULL REFERENCES ventas_region(id) ON DELETE SET NULL;
    """)
    print("   ✓ Columna region_id agregada")
else:
    print("   ⚠️  Columna region_id ya existe (skip)")

if 'comuna_id' not in columnas_existentes:
    cursor.execute("""
        ALTER TABLE ventas_cliente
        ADD COLUMN comuna_id INTEGER NULL REFERENCES ventas_comuna(id) ON DELETE SET NULL;
    """)
    print("   ✓ Columna comuna_id agregada")
else:
    print("   ⚠️  Columna comuna_id ya existe (skip)")

# ============================================
# 4. CREAR ÍNDICES
# ============================================
print("\n4️⃣  Creando índices...")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS ventas_region_codigo_idx ON ventas_region(codigo);
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS ventas_comuna_region_id_idx ON ventas_comuna(region_id);
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS ventas_cliente_region_id_idx ON ventas_cliente(region_id);
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS ventas_cliente_comuna_id_idx ON ventas_cliente(comuna_id);
""")

print("   ✓ Índices creados")

# ============================================
# 5. VERIFICACIÓN FINAL
# ============================================
print("\n" + "="*100)
print("VERIFICACIÓN FINAL")
print("="*100)

cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'ventas_region'
    );
""")
region_exists = cursor.fetchone()[0]

cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'ventas_comuna'
    );
""")
comuna_exists = cursor.fetchone()[0]

cursor.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'ventas_cliente'
    AND column_name IN ('region_id', 'comuna_id');
""")
columnas = [row[0] for row in cursor.fetchall()]

print(f"\n✅ Tabla ventas_region existe: {region_exists}")
print(f"✅ Tabla ventas_comuna existe: {comuna_exists}")
print(f"✅ Columnas en ventas_cliente: {', '.join(columnas)}")

print("\n" + "="*100)
print("✅ ¡TABLAS Y COLUMNAS CREADAS EXITOSAMENTE!")
print("="*100)

print("""
PRÓXIMOS PASOS:

1. Marcar migración 0057 como aplicada:
   python manage.py migrate ventas 0057 --fake

2. Cargar fixtures de regiones y comunas:
   python manage.py loaddata regiones_comunas_chile

3. Migrar datos de clientes:
   python manage.py shell < scripts/migrar_clientes_a_region_comuna.py
""")

print("="*100 + "\n")
