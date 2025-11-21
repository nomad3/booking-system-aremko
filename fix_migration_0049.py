#!/usr/bin/env python
"""
Script para registrar la migración 0049 en django_migrations.

Este script resuelve el error:
InconsistentMigrationHistory: Migration ventas.0050_homepagesettings is applied
before its dependency ventas.0049_campaigninteraction

IMPORTANTE: Solo registra que la migración fue aplicada, NO ejecuta SQL.
Esto es seguro porque la tabla ventas_campaigninteraction ya existe en producción.

Uso:
    python fix_migration_0049.py
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

def fix_migration_0049():
    """Registra la migración 0049 en django_migrations"""

    print("=" * 60)
    print("🔧 Fix de Migración 0049")
    print("=" * 60)

    # Verificar si ya está registrada
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) FROM django_migrations
            WHERE app = 'ventas' AND name = '0049_campaigninteraction'
        """)
        count = cursor.fetchone()[0]

        if count > 0:
            print("⚠️  La migración 0049 ya está registrada.")
            print("   No es necesario hacer nada.")
            return

    # Insertar el registro
    print("\n📝 Insertando registro de migración 0049...")

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO django_migrations (app, name, applied)
                VALUES ('ventas', '0049_campaigninteraction', NOW())
            """)

        print("✅ Migración 0049 registrada exitosamente")
        print("\n" + "=" * 60)
        print("🎯 Ahora puedes ejecutar:")
        print("   python manage.py migrate ventas")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error al insertar registro: {e}")
        print("\nIntenta ejecutar este SQL manualmente en dbshell:")
        print("   python manage.py dbshell")
        print("   INSERT INTO django_migrations (app, name, applied)")
        print("   VALUES ('ventas', '0049_campaigninteraction', NOW());")
        sys.exit(1)

if __name__ == '__main__':
    fix_migration_0049()
