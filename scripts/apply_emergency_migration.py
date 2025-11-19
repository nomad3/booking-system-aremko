#!/usr/bin/env python
"""
Script para aplicar la migración de EMERGENCY de forma segura
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.db import connection
from django.core.management import call_command

def check_emergency_value():
    """Verificar si EMERGENCY ya existe en la base de datos"""
    with connection.cursor() as cursor:
        try:
            # Verificar si el valor EMERGENCY existe en alguna tarea
            cursor.execute("""
                SELECT COUNT(*)
                FROM control_gestion_task
                WHERE time_criticality = 'EMERGENCY'
            """)
            count = cursor.fetchone()[0]
            print(f"✓ Tareas con EMERGENCY encontradas: {count}")
            return True
        except Exception as e:
            print(f"✗ Error verificando EMERGENCY: {e}")
            return False

def check_migration_applied():
    """Verificar si la migración ya fue aplicada"""
    with connection.cursor() as cursor:
        try:
            cursor.execute("""
                SELECT name
                FROM django_migrations
                WHERE app = 'control_gestion'
                AND name = '0005_add_emergency_time_criticality'
            """)
            result = cursor.fetchone()
            if result:
                print("✓ Migración 0005_add_emergency_time_criticality ya aplicada")
                return True
            else:
                print("✗ Migración 0005_add_emergency_time_criticality NO aplicada")
                return False
        except Exception as e:
            print(f"✗ Error verificando migración: {e}")
            return False

def main():
    print("=== Verificación de migración EMERGENCY ===\n")

    # 1. Verificar si la migración ya fue aplicada
    migration_applied = check_migration_applied()

    # 2. Verificar si el valor EMERGENCY funciona
    emergency_works = check_emergency_value()

    # 3. Si la migración no está aplicada, intentar aplicarla
    if not migration_applied:
        print("\n¿Desea aplicar la migración ahora? (s/n): ", end='')
        response = input().strip().lower()

        if response == 's':
            try:
                print("\nAplicando migración...")
                call_command('migrate', 'control_gestion', '0005_add_emergency_time_criticality')
                print("✓ Migración aplicada exitosamente")
            except Exception as e:
                print(f"✗ Error aplicando migración: {e}")
                print("\nIntente aplicar manualmente con:")
                print("python manage.py migrate control_gestion 0005_add_emergency_time_criticality")

    print("\n=== Resumen ===")
    print(f"Migración aplicada: {'Sí' if migration_applied else 'No'}")
    print(f"EMERGENCY funciona: {'Sí' if emergency_works else 'No'}")

if __name__ == "__main__":
    main()