#!/usr/bin/env python
"""
Script SEGURO para eliminar columnas redundantes de ServicioBloqueo
Incluye backup y verificación
"""
import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection, transaction
import json

print("=== FIX SEGURO PARA SERVICIOBLOQUEO ===\n")
print("Este script:")
print("1. Hace backup de los datos actuales")
print("2. Elimina las columnas redundantes")
print("3. Verifica el resultado\n")

def hacer_backup(cursor):
    """Crea un backup JSON de los datos actuales"""
    print("1. Creando backup de datos...")

    cursor.execute("""
        SELECT id, servicio_id, fecha_inicio, fecha_fin, fecha, hora_slot,
               motivo, activo, notas, creado_en, created_at
        FROM ventas_serviciobloqueo
        ORDER BY id
    """)

    datos = []
    for row in cursor.fetchall():
        datos.append({
            'id': row[0],
            'servicio_id': row[1],
            'fecha_inicio': str(row[2]),
            'fecha_fin': str(row[3]),
            'fecha': str(row[4]) if row[4] else None,
            'hora_slot': row[5],
            'motivo': row[6],
            'activo': row[7],
            'notas': row[8],
            'creado_en': str(row[9]),
            'created_at': str(row[10]) if row[10] else None
        })

    # Guardar backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'backup_serviciobloqueo_{timestamp}.json'

    with open(filename, 'w') as f:
        json.dump(datos, f, indent=2)

    print(f"   ✅ Backup guardado en: {filename}")
    print(f"   Total registros respaldados: {len(datos)}")
    return filename

try:
    with transaction.atomic():
        with connection.cursor() as cursor:
            # 1. Hacer backup
            backup_file = hacer_backup(cursor)

            # 2. Confirmar antes de proceder
            print("\n2. ¿Proceder con la eliminación de columnas redundantes?")
            print("   Columnas a eliminar: fecha, hora_slot, created_at, updated_at")
            respuesta = input("   Escriba 'SI' para continuar: ")

            if respuesta != 'SI':
                print("\n   ❌ Operación cancelada")
                exit(0)

            # 3. Eliminar columnas
            print("\n3. Eliminando columnas redundantes...")

            columnas_a_eliminar = ['fecha', 'hora_slot', 'created_at', 'updated_at']
            for columna in columnas_a_eliminar:
                try:
                    cursor.execute(f"ALTER TABLE ventas_serviciobloqueo DROP COLUMN {columna}")
                    print(f"   ✅ Eliminada columna: {columna}")
                except Exception as e:
                    print(f"   ⚠️  No se pudo eliminar {columna}: {str(e)}")

            # 4. Verificar resultado
            print("\n4. Verificando resultado...")

            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'ventas_serviciobloqueo'
                ORDER BY ordinal_position
            """)

            columnas_finales = [col[0] for col in cursor.fetchall()]
            print(f"   Columnas finales: {', '.join(columnas_finales)}")

            # Verificar que las columnas problemáticas ya no existen
            problematicas = set(columnas_a_eliminar) & set(columnas_finales)
            if problematicas:
                print(f"   ❌ ERROR: Aún existen columnas problemáticas: {problematicas}")
                raise Exception("No se eliminaron todas las columnas")

            # 5. Test final - verificar que podemos consultar la tabla
            print("\n5. Test final...")
            cursor.execute("SELECT COUNT(*) FROM ventas_serviciobloqueo")
            count = cursor.fetchone()[0]
            print(f"   ✅ La tabla funciona correctamente")
            print(f"   Total registros: {count}")

            print("\n✅ FIX COMPLETADO EXITOSAMENTE")
            print(f"\n📁 Backup guardado en: {backup_file}")
            print("   Si algo sale mal, contacta al administrador con este archivo")

except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    print("   La transacción fue revertida, no se hicieron cambios")
    import traceback
    traceback.print_exc()

print("\n=== FIN DEL FIX ===")