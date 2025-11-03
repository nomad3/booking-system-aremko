#!/usr/bin/env python
"""
Script simple para verificar campos de Premio en producción
"""
import os
import django

# Setup Django con el settings correcto para producción
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection
from ventas.models import Premio

def main():
    print("=== VERIFICANDO COLUMNAS DE LA TABLA PREMIO ===")

    try:
        with connection.cursor() as cursor:
            # Obtener todas las columnas de la tabla
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'ventas_premio'
                ORDER BY ordinal_position
            """)
            columns = [col[0] for col in cursor.fetchall()]

            print(f"\nTotal de columnas: {len(columns)}")
            print("Columnas encontradas:")
            for col in columns:
                print(f"  - {col}")

            # Verificar si existe tramos_validos
            if 'tramos_validos' in columns:
                print("\n✅ El campo 'tramos_validos' SÍ existe en la base de datos")
            else:
                print("\n❌ El campo 'tramos_validos' NO existe en la base de datos")
                print("   Necesitas crear una migración para agregarlo")

    except Exception as e:
        print(f"Error al verificar columnas: {e}")

    print("\n=== VERIFICANDO DATOS DE PREMIOS ===")

    try:
        # Contar premios
        total_premios = Premio.objects.count()
        print(f"Total de premios en la BD: {total_premios}")

        # Verificar primer premio
        if total_premios > 0:
            premio = Premio.objects.first()
            print(f"\nPrimer premio encontrado:")
            print(f"  - Nombre: {premio.nombre}")
            print(f"  - Tipo: {premio.tipo}")
            print(f"  - Tramo hito: {premio.tramo_hito}")

            # Intentar acceder a tramos_validos
            try:
                valor_tramos = premio.tramos_validos
                print(f"  - Tramos válidos: {valor_tramos}")
            except AttributeError:
                print("  - Tramos válidos: Campo no existe en el modelo")
            except Exception as e:
                print(f"  - Tramos válidos: Error al acceder - {e}")
        else:
            print("No hay premios en la base de datos")

    except Exception as e:
        print(f"Error al verificar premios: {e}")

    print("\n=== RESUMEN Y PRÓXIMOS PASOS ===")
    print("Si el campo 'tramos_validos' no existe en la BD:")
    print("1. Crear archivo de migración manualmente")
    print("2. python manage.py migrate ventas")
    print("3. python manage.py configurar_tramos_premios")

if __name__ == "__main__":
    main()