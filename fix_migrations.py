#!/usr/bin/env python
"""
Script para verificar y corregir problemas con las migraciones 0069 y 0070
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

def check_migrations():
    """Verificar el estado de las migraciones"""

    print("=" * 60)
    print("VERIFICACIÓN DE MIGRACIONES")
    print("=" * 60)

    # 1. Verificar archivos de migración
    migrations_dir = "ventas/migrations"
    print("\n1. ARCHIVOS DE MIGRACIÓN ENCONTRADOS:")
    print("-" * 40)

    migration_files = []
    for file in sorted(os.listdir(migrations_dir)):
        if file.endswith('.py') and file != '__init__.py':
            filepath = os.path.join(migrations_dir, file)
            file_stat = os.stat(filepath)
            perms = oct(file_stat.st_mode)[-3:]
            migration_files.append(file)

            # Marcar archivos problemáticos
            status = ""
            if "0069" in file:
                status = " ← MIGRACIÓN 0069"
            elif "0070" in file:
                status = " ← MIGRACIÓN 0070"
            elif ".disabled" in file:
                status = " (DESHABILITADO)"

            print(f"  {file} (permisos: {perms}){status}")

    # 2. Verificar migraciones aplicadas en la base de datos
    print("\n2. ÚLTIMAS MIGRACIONES APLICADAS EN LA BASE DE DATOS:")
    print("-" * 40)

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT name, applied
                FROM django_migrations
                WHERE app = 'ventas'
                ORDER BY name DESC
                LIMIT 10
            """)
            results = cursor.fetchall()

            for name, applied in results:
                print(f"  {name} - Aplicada: {applied}")

            # Obtener la última migración aplicada
            cursor.execute("""
                SELECT name
                FROM django_migrations
                WHERE app = 'ventas'
                ORDER BY name DESC
                LIMIT 1
            """)
            last_migration = cursor.fetchone()
            if last_migration:
                print(f"\n  → Última migración aplicada: {last_migration[0]}")
    except Exception as e:
        print(f"  Error al consultar la base de datos: {e}")

    # 3. Verificar conflictos
    print("\n3. VERIFICACIÓN DE CONFLICTOS:")
    print("-" * 40)

    # Buscar migraciones duplicadas
    migration_numbers = {}
    for file in migration_files:
        if file.startswith('00'):
            number = file[:4]
            if number not in migration_numbers:
                migration_numbers[number] = []
            migration_numbers[number].append(file)

    conflicts = False
    for number, files in migration_numbers.items():
        if len(files) > 1:
            conflicts = True
            print(f"  ⚠️ CONFLICTO: Múltiples migraciones con número {number}:")
            for f in files:
                print(f"     - {f}")

    if not conflicts:
        print("  ✓ No hay conflictos de numeración")

    # 4. Sugerencias de solución
    print("\n4. SOLUCIONES SUGERIDAS:")
    print("-" * 40)

    # Verificar si 0069 existe
    has_0069 = any("0069" in f for f in migration_files)
    has_0070 = any("0070" in f for f in migration_files)

    if not has_0069:
        print("  ⚠️ La migración 0069 NO existe en el directorio")
        print("  → Solución: Copiar el archivo 0069_agregar_configuracion_resumen.py al servidor")
    else:
        print("  ✓ La migración 0069 existe")

    if not has_0070:
        print("  ⚠️ La migración 0070 NO existe en el directorio")
        print("  → Solución: Copiar el archivo 0070_agregar_configuracion_tips.py al servidor")
    else:
        print("  ✓ La migración 0070 existe")

    # Verificar permisos
    for file in migration_files:
        if "0069" in file or "0070" in file:
            filepath = os.path.join(migrations_dir, file)
            file_stat = os.stat(filepath)
            perms = file_stat.st_mode & 0o777
            if perms != 0o644:
                print(f"  ⚠️ {file} tiene permisos incorrectos: {oct(perms)}")
                print(f"  → Ejecutar: chmod 644 {filepath}")

    print("\n" + "=" * 60)
    print("COMANDOS RECOMENDADOS PARA EL SERVIDOR:")
    print("=" * 60)

    print("""
1. Asegurarse de que los archivos de migración estén en el servidor:
   scp ventas/migrations/0069_agregar_configuracion_resumen.py servidor:/app/ventas/migrations/
   scp ventas/migrations/0070_agregar_configuracion_tips.py servidor:/app/ventas/migrations/

2. Corregir permisos en el servidor:
   chmod 644 ventas/migrations/0069_agregar_configuracion_resumen.py
   chmod 644 ventas/migrations/0070_agregar_configuracion_tips.py

3. Si la migración 0068 ya está aplicada, ejecutar:
   python manage.py migrate ventas 0069
   python manage.py migrate ventas 0070

4. Si hay problemas con las dependencias:
   python manage.py migrate ventas 0069 --fake
   python manage.py migrate ventas 0070
""")

if __name__ == "__main__":
    check_migrations()