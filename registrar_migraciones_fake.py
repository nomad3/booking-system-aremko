#!/usr/bin/env python
"""
Script para registrar todas las migraciones pendientes como 'fake' aplicadas.

Este script es seguro porque:
1. Solo registra en django_migrations que las migraciones están aplicadas
2. NO ejecuta SQL (no crea/modifica tablas)
3. Asume que las tablas ya existen en producción

Usar cuando:
- El historial de django_migrations está inconsistente
- Las tablas ya existen en la BD
- Quieres volver a usar 'python manage.py migrate' normalmente

Uso:
    python registrar_migraciones_fake.py
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder

def registrar_migraciones_fake():
    """Registra todas las migraciones pendientes como fake"""

    print("=" * 70)
    print("📝 Registro de Migraciones como Fake")
    print("=" * 70)
    print()
    print("⚠️  Este script registra migraciones sin ejecutar SQL.")
    print("   Útil cuando las tablas ya existen pero faltan registros.")
    print()

    try:
        # Cargar el loader de migraciones
        loader = MigrationLoader(connection)
        recorder = MigrationRecorder(connection)

        # Obtener todas las migraciones del grafo
        all_migrations = set(loader.graph.nodes.keys())

        # Obtener migraciones ya aplicadas (es un dict, convertir a set de keys)
        applied_migrations = set(recorder.applied_migrations())

        # Calcular pendientes
        pending = all_migrations - applied_migrations

        if not pending:
            print("✅ No hay migraciones pendientes. Todo está registrado.")
            return

        # Filtrar solo ventas y control_gestion
        pending_filtered = [m for m in pending if m[0] in ['ventas', 'control_gestion']]

        if not pending_filtered:
            print("✅ No hay migraciones de ventas/control_gestion pendientes.")
            return

        print(f"📦 Migraciones pendientes a registrar: {len(pending_filtered)}")
        for app, name in sorted(pending_filtered):
            print(f"   → {app}.{name}")

        print("\n🚀 Registrando migraciones como fake...")
        print("-" * 70)

        # Registrar cada migración
        for app_label, migration_name in sorted(pending_filtered):
            try:
                print(f"   📝 {app_label}.{migration_name}...", end=" ")

                # Verificar si ya existe
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT COUNT(*) FROM django_migrations
                        WHERE app = %s AND name = %s
                    """, [app_label, migration_name])

                    count = cursor.fetchone()[0]

                    if count > 0:
                        print("⏭️  (ya existe)")
                        continue

                    # Insertar registro en django_migrations
                    cursor.execute("""
                        INSERT INTO django_migrations (app, name, applied)
                        VALUES (%s, %s, NOW())
                    """, [app_label, migration_name])

                print("✅")

            except Exception as e:
                print(f"❌ Error: {e}")
                continue

        print("\n" + "=" * 70)
        print("🎉 ¡Migraciones registradas exitosamente!")
        print("=" * 70)
        print()
        print("🎯 Ahora puedes usar comandos normales de Django:")
        print("   python manage.py showmigrations ventas")
        print("   python manage.py migrate ventas")
        print()
        print("📋 Para poblar las GiftCard experiencias:")
        print("   python poblar_experiencias_giftcard.py")
        print()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    registrar_migraciones_fake()
