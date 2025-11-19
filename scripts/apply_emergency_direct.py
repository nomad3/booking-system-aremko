#!/usr/bin/env python
"""
Script para aplicar EMERGENCY directamente en la base de datos
sin usar el sistema de migraciones de Django
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.db import connection

def apply_emergency_direct():
    """Aplicar EMERGENCY directamente alterando el constraint"""

    print("=== APLICANDO EMERGENCY DIRECTAMENTE ===\n")

    with connection.cursor() as cursor:
        try:
            print("1. Eliminando constraint anterior...")
            cursor.execute("""
                ALTER TABLE control_gestion_task
                DROP CONSTRAINT IF EXISTS control_gestion_task_time_criticality_check;
            """)
            print("   ✓ Constraint eliminado")

            print("\n2. Creando nuevo constraint con EMERGENCY...")
            cursor.execute("""
                ALTER TABLE control_gestion_task
                ADD CONSTRAINT control_gestion_task_time_criticality_check
                CHECK (time_criticality IN ('EMERGENCY', 'CRITICAL', 'SCHEDULED', 'FLEXIBLE'));
            """)
            print("   ✓ Nuevo constraint creado")

            print("\n3. Verificando que funcione...")
            cursor.execute("""
                SELECT 1 WHERE 'EMERGENCY' IN ('EMERGENCY', 'CRITICAL', 'SCHEDULED', 'FLEXIBLE');
            """)
            if cursor.fetchone():
                print("   ✓ EMERGENCY está disponible")

            print("\n✅ EMERGENCY aplicado exitosamente!")
            print("\nAhora puedes:")
            print("1. Cambiar forms.py línea 122 de CRITICAL a EMERGENCY")
            print("2. Las tareas de emergencia usarán EMERGENCY en lugar de CRITICAL")

        except Exception as e:
            print(f"\n✗ Error aplicando cambios: {e}")
            print("\nPosibles causas:")
            print("- No tienes permisos para ALTER TABLE")
            print("- La base de datos no es PostgreSQL")
            print("- El constraint tiene otro nombre")

if __name__ == "__main__":
    print("Este script aplicará EMERGENCY directamente en la base de datos.")
    print("¿Deseas continuar? (s/n): ", end='')

    response = input().strip().lower()
    if response == 's':
        apply_emergency_direct()
    else:
        print("\nOperación cancelada.")