#!/usr/bin/env python
"""
Script para solucionar el problema de la migración de tramo_hito
Ejecutar en Render Shell: python scripts/fix_premio_migration.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestor_talleres.settings')
django.setup()

from django.db import connection

print("=" * 80)
print("🔧 FIX: Migración manual de campo tramo_hito")
print("=" * 80)
print()

# Paso 1: Verificar si la columna ya existe
print("📋 PASO 1: Verificando si la columna tramo_hito ya existe...")
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='ventas_premio' AND column_name='tramo_hito';
    """)
    exists = cursor.fetchone()

if exists:
    print("   ✅ La columna 'tramo_hito' YA EXISTE")
    print("   ℹ️  No es necesario agregar la columna\n")
else:
    print("   ⚠️  La columna 'tramo_hito' NO EXISTE")
    print("   ➕ Agregando columna...\n")

    # Paso 2: Agregar la columna
    print("📋 PASO 2: Agregando columna tramo_hito a ventas_premio...")
    with connection.cursor() as cursor:
        cursor.execute("""
            ALTER TABLE ventas_premio
            ADD COLUMN tramo_hito INTEGER NULL;
        """)
    print("   ✅ Columna agregada exitosamente\n")

# Paso 3: Registrar la migración en django_migrations
print("📋 PASO 3: Registrando migración en django_migrations...")
with connection.cursor() as cursor:
    # Verificar si ya está registrada
    cursor.execute("""
        SELECT id FROM django_migrations
        WHERE app='ventas' AND name='0058_add_tramo_hito_to_premio';
    """)
    registered = cursor.fetchone()

    if registered:
        print("   ✅ La migración YA ESTÁ REGISTRADA")
    else:
        cursor.execute("""
            INSERT INTO django_migrations (app, name, applied)
            VALUES ('ventas', '0058_add_tramo_hito_to_premio', NOW());
        """)
        print("   ✅ Migración registrada exitosamente")

print()

# Paso 4: Poblar datos iniciales
print("📋 PASO 4: Poblando datos iniciales...")
from ventas.models import Premio

updates = [
    (2, 5, "Vale $60K"),
    (3, 10, "Noche VIP"),
    (4, 15, "Vale Premium"),
    (5, 20, "Noche Elite"),
]

for premio_id, tramo, nombre in updates:
    updated = Premio.objects.filter(id=premio_id).update(tramo_hito=tramo)
    if updated:
        print(f"   ✅ Premio ID {premio_id} ({nombre}) → Tramo {tramo}")
    else:
        print(f"   ⚠️  Premio ID {premio_id} no encontrado")

print()

# Paso 5: Verificar resultado
print("📋 PASO 5: Verificación final...")
premios = Premio.objects.all()
print()
for p in premios:
    tramo_desc = p.descripcion_tramo() if hasattr(p, 'descripcion_tramo') else f"Tramo {p.tramo_hito}"
    print(f"   ID {p.id}: {p.nombre[:40]:<40} → {tramo_desc}")

print()
print("=" * 80)
print("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
print("=" * 80)
print()
print("📌 El módulo de premios debería funcionar ahora.")
print("📌 Recarga la página en el navegador para verificar.")
print()
