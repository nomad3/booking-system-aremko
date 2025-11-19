#!/usr/bin/env python
"""
Script para verificar el estado de EMERGENCY en la base de datos
sin depender de las migraciones de Django
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.db import connection
from control_gestion.models import Task, TimeCriticality

def check_emergency_status():
    """Verificar el estado completo de EMERGENCY en el sistema"""

    print("=== VERIFICACIÓN DE ESTADO DE EMERGENCY ===\n")

    # 1. Verificar si EMERGENCY existe en el modelo Python
    print("1. Verificando modelo Python (TimeCriticality):")
    try:
        choices = dict(TimeCriticality.choices)
        print(f"   Opciones disponibles: {list(choices.keys())}")
        if 'EMERGENCY' in choices:
            print("   ✓ EMERGENCY existe en el modelo Python")
        else:
            print("   ✗ EMERGENCY NO existe en el modelo Python")
    except Exception as e:
        print(f"   ✗ Error verificando modelo: {e}")

    # 2. Verificar constraint en la base de datos
    print("\n2. Verificando constraint en la base de datos:")
    with connection.cursor() as cursor:
        try:
            # Para PostgreSQL
            cursor.execute("""
                SELECT
                    con.conname as constraint_name,
                    pg_get_constraintdef(con.oid) as definition
                FROM pg_constraint con
                INNER JOIN pg_class rel ON rel.oid = con.conrelid
                INNER JOIN pg_namespace nsp ON nsp.oid = con.connamespace
                WHERE rel.relname = 'control_gestion_task'
                AND con.contype = 'c'
                AND pg_get_constraintdef(con.oid) LIKE '%time_criticality%'
            """)

            constraints = cursor.fetchall()
            if constraints:
                for name, definition in constraints:
                    print(f"   Constraint: {name}")
                    print(f"   Definición: {definition}")
                    if 'EMERGENCY' in definition:
                        print("   ✓ EMERGENCY está incluido en el constraint")
                    else:
                        print("   ✗ EMERGENCY NO está en el constraint")
            else:
                print("   ✗ No se encontró constraint para time_criticality")

        except Exception as e:
            print(f"   ✗ Error verificando constraints: {e}")

    # 3. Verificar si hay tareas con EMERGENCY
    print("\n3. Verificando tareas existentes:")
    with connection.cursor() as cursor:
        try:
            # Contar por cada tipo
            cursor.execute("""
                SELECT time_criticality, COUNT(*)
                FROM control_gestion_task
                GROUP BY time_criticality
                ORDER BY time_criticality
            """)

            results = cursor.fetchall()
            if results:
                for criticality, count in results:
                    print(f"   {criticality}: {count} tareas")
            else:
                print("   No hay tareas en el sistema")

            # Intentar buscar EMERGENCY específicamente
            try:
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM control_gestion_task
                    WHERE time_criticality = 'EMERGENCY'
                """)
                emergency_count = cursor.fetchone()[0]
                print(f"\n   Tareas con EMERGENCY: {emergency_count}")
            except Exception as e:
                print(f"\n   ✗ No se puede buscar EMERGENCY: {str(e)}")

        except Exception as e:
            print(f"   ✗ Error contando tareas: {e}")

    # 4. Verificar tabla de migraciones
    print("\n4. Verificando tabla de migraciones:")
    with connection.cursor() as cursor:
        try:
            cursor.execute("""
                SELECT name, applied
                FROM django_migrations
                WHERE app = 'control_gestion'
                AND name LIKE '%emergency%'
                ORDER BY applied DESC
            """)

            migrations = cursor.fetchall()
            if migrations:
                for name, applied in migrations:
                    print(f"   {name}: aplicada el {applied}")
            else:
                print("   ✗ No se encontró migración de EMERGENCY")

        except Exception as e:
            print(f"   ✗ Error verificando migraciones: {e}")

    # 5. Probar crear una tarea con EMERGENCY
    print("\n5. Prueba de creación con EMERGENCY:")
    try:
        # Intentar crear una tarea temporal con EMERGENCY
        from django.contrib.auth import get_user_model
        User = get_user_model()

        test_task = Task(
            title="TEST EMERGENCY - BORRAR",
            description="Prueba temporal",
            time_criticality='EMERGENCY',
            priority='ALTA',
            queue_position=999,
            state='BACKLOG'
        )

        # Validar sin guardar
        test_task.full_clean()
        print("   ✓ Se puede crear una tarea con EMERGENCY (validación pasó)")

    except Exception as e:
        print(f"   ✗ NO se puede crear con EMERGENCY: {str(e)}")

    print("\n" + "="*50)
    print("\nRESUMEN:")
    print("Si necesitas aplicar EMERGENCY manualmente, usa:")
    print("python scripts/fix_emergency_migration.py")

if __name__ == "__main__":
    check_emergency_status()