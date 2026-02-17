import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

print("=== ARREGLAR SERVICIOBLOQUEO ===\n")

cursor = connection.cursor()

try:
    # Verificar columnas actuales
    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'ventas_serviciobloqueo'")
    columnas = [col[0] for col in cursor.fetchall()]
    print(f"Columnas actuales: {columnas}")

    if 'fecha' not in columnas and 'fecha_inicio' in columnas:
        print("\n⚠️  Detectado: tabla tiene 'fecha_inicio' pero código busca 'fecha'")

        respuesta = input("\n¿Agregar columna 'fecha' copiando datos de 'fecha_inicio'? (s/n): ")

        if respuesta.lower() == 's':
            print("\nEjecutando fix...")

            # Agregar columna fecha
            cursor.execute("ALTER TABLE ventas_serviciobloqueo ADD COLUMN IF NOT EXISTS fecha DATE")
            print("✅ Columna 'fecha' agregada")

            # Copiar datos de fecha_inicio a fecha
            cursor.execute("UPDATE ventas_serviciobloqueo SET fecha = fecha_inicio WHERE fecha IS NULL")
            print("✅ Datos copiados de fecha_inicio a fecha")

            # Commit cambios
            connection.commit()
            print("\n✅ Fix aplicado exitosamente")
            print("El calendario debería funcionar ahora.")
        else:
            print("\nFix cancelado.")

    elif 'fecha' in columnas:
        print("\n✅ La columna 'fecha' ya existe. No hay nada que arreglar.")

    else:
        print("\n❌ Estructura de tabla no reconocida. Columnas:", columnas)

except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    connection.rollback()

print("\n=== FIN ===")