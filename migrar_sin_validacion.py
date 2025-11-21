#!/usr/bin/env python
"""
Script para aplicar migraciones saltando la validación de consistencia.

Este script aplica las migraciones que realmente faltan sin validar
el historial de django_migrations, resolviendo problemas de
InconsistentMigrationHistory.

IMPORTANTE: Solo aplica migraciones nuevas, no re-ejecuta las existentes.
Es seguro porque Django detecta qué tablas ya existen.

Uso:
    python migrar_sin_validacion.py
"""

import os
import sys
import django
from django.core.management import call_command

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection
from django.db.migrations.executor import MigrationExecutor

def listar_migraciones_pendientes():
    """Lista las migraciones que Django detecta como pendientes"""

    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()

    # Deshabilitar el check de consistencia temporalmente
    plan = executor.migration_plan(targets)

    return plan

def aplicar_migraciones():
    """Aplica las migraciones pendientes sin validar consistencia"""

    print("=" * 70)
    print("🔧 Migración sin Validación de Historial")
    print("=" * 70)
    print()
    print("⚠️  Este script aplica migraciones saltando la validación de consistencia.")
    print("   Solo aplica migraciones NUEVAS (que no han sido ejecutadas).")
    print()

    # Obtener migraciones pendientes
    print("📋 Detectando migraciones pendientes...")

    try:
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()

        # Obtener plan SIN ejecutar check_consistent_history
        plan = executor.migration_plan(targets)

        if not plan:
            print("✅ No hay migraciones pendientes. Todo está al día.")
            return

        print(f"\n📦 Migraciones a aplicar: {len(plan)}")
        for migration, backwards in plan:
            print(f"   → {migration.app_label}.{migration.name}")

        print("\n🚀 Aplicando migraciones...")
        print("-" * 70)

        # Ejecutar migraciones una por una
        for migration, backwards in plan:
            app_label = migration.app_label
            migration_name = migration.name

            print(f"\n⏳ Aplicando {app_label}.{migration_name}...")

            try:
                # Ejecutar la migración específica
                executor.apply_migration(
                    executor.loader.graph.nodes[(app_label, migration_name)],
                    fake=False
                )
                print(f"   ✅ {app_label}.{migration_name} aplicada correctamente")

            except Exception as e:
                # Si falla porque la tabla ya existe, marcarla como fake
                error_msg = str(e).lower()
                if 'already exists' in error_msg or 'duplicate' in error_msg:
                    print(f"   ⚠️  Tabla ya existe, registrando como aplicada (fake)...")
                    executor.apply_migration(
                        executor.loader.graph.nodes[(app_label, migration_name)],
                        fake=True
                    )
                    print(f"   ✅ {app_label}.{migration_name} registrada (fake)")
                else:
                    print(f"   ❌ Error: {e}")
                    raise

        print("\n" + "=" * 70)
        print("🎉 ¡Migraciones aplicadas exitosamente!")
        print("=" * 70)
        print("\n🎯 Ahora puedes ejecutar:")
        print("   python poblar_experiencias_giftcard.py")
        print()

    except Exception as e:
        print(f"\n❌ Error durante la migración: {e}")
        print("\n💡 Solución alternativa:")
        print("   Contacta al equipo técnico para revisar manualmente la BD.")
        sys.exit(1)

if __name__ == '__main__':
    aplicar_migraciones()
