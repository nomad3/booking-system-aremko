#!/usr/bin/env python
"""
Script para aplicar la migración de EMERGENCY de forma manual si falla el comando migrate.

Este script:
1. Verifica si la migración está aplicada
2. Si no, la aplica manualmente agregando el valor EMERGENCY a la base de datos
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.db import connection

def check_emergency_in_db():
    """Verificar si EMERGENCY existe en los constraints de la base de datos"""
    with connection.cursor() as cursor:
        try:
            # Verificar si existe el constraint con EMERGENCY
            cursor.execute("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'control_gestion_task'
                AND constraint_type = 'CHECK'
            """)

            constraints = cursor.fetchall()
            print(f"Constraints encontrados: {len(constraints)}")

            # Verificar si alguna tarea ya tiene EMERGENCY
            cursor.execute("""
                SELECT COUNT(*)
                FROM control_gestion_task
                WHERE time_criticality = 'EMERGENCY'
            """)
            count = cursor.fetchone()[0]
            print(f"Tareas con EMERGENCY: {count}")

            return True
        except Exception as e:
            print(f"Error verificando EMERGENCY: {e}")
            return False

def apply_emergency_manually():
    """Aplicar el cambio manualmente si la migración falla"""
    with connection.cursor() as cursor:
        try:
            # Primero, eliminar el constraint existente si existe
            cursor.execute("""
                ALTER TABLE control_gestion_task
                DROP CONSTRAINT IF EXISTS control_gestion_task_time_criticality_check
            """)
            print("✓ Constraint anterior eliminado")

            # Crear nuevo constraint que incluye EMERGENCY
            cursor.execute("""
                ALTER TABLE control_gestion_task
                ADD CONSTRAINT control_gestion_task_time_criticality_check
                CHECK (time_criticality IN ('EMERGENCY', 'CRITICAL', 'SCHEDULED', 'FLEXIBLE'))
            """)
            print("✓ Nuevo constraint creado con EMERGENCY")

            # Marcar la migración como aplicada
            cursor.execute("""
                INSERT INTO django_migrations (app, name, applied)
                VALUES ('control_gestion', '0005_add_emergency_time_criticality', NOW())
                ON CONFLICT DO NOTHING
            """)
            print("✓ Migración marcada como aplicada")

            return True
        except Exception as e:
            print(f"✗ Error aplicando cambios: {e}")
            return False

def main():
    print("=== Aplicando corrección de EMERGENCY ===\n")

    # 1. Verificar estado actual
    print("1. Verificando estado actual...")
    check_emergency_in_db()

    # 2. Preguntar si aplicar manualmente
    print("\n¿Desea aplicar la corrección manualmente? (s/n): ", end='')
    response = input().strip().lower()

    if response == 's':
        print("\n2. Aplicando corrección...")
        if apply_emergency_manually():
            print("\n✓ Corrección aplicada exitosamente")
            print("Las tareas de emergencia ahora deberían funcionar correctamente.")
        else:
            print("\n✗ Error al aplicar la corrección")
            print("Por favor, contacte al administrador del sistema.")
    else:
        print("\nOperación cancelada.")

if __name__ == "__main__":
    main()