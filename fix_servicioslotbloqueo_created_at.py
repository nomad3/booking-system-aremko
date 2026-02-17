import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

print("=== ARREGLAR CREATED_AT EN SERVICIOSLOTBLOQUEO ===\n")

cursor = connection.cursor()

try:
    # 1. Verificar si la tabla existe
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'ventas_servicioslotbloqueo'
        )
    """)
    existe_tabla = cursor.fetchone()[0]

    if not existe_tabla:
        print("❌ La tabla ventas_servicioslotbloqueo NO existe")
        print("Esto indica un problema mayor con las migraciones.")
    else:
        print("✅ La tabla ventas_servicioslotbloqueo existe")

        # 2. Ver qué columnas tiene
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'ventas_servicioslotbloqueo'
            ORDER BY column_name
        """)
        columnas = [col[0] for col in cursor.fetchall()]
        print(f"\nColumnas actuales: {columnas}")

        # 3. Verificar si created_at existe
        if 'created_at' not in columnas:
            print("\n❌ Falta columna 'created_at'")

            respuesta = input("\n¿Agregar columna created_at? (s/n): ")

            if respuesta.lower() == 's':
                print("\nAgregando columna created_at...")

                # Agregar created_at con valor por defecto
                cursor.execute("""
                    ALTER TABLE ventas_servicioslotbloqueo
                    ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                """)
                connection.commit()
                print("✅ Columna created_at agregada")

                # Verificar si también necesita updated_at, activo, etc.
                print("\nVerificando otras columnas que podrían faltar...")

                columnas_comunes = ['updated_at', 'activo']
                for col in columnas_comunes:
                    if col not in columnas:
                        print(f"\n❌ También falta columna '{col}'")
                        if col == 'updated_at':
                            cursor.execute("""
                                ALTER TABLE ventas_servicioslotbloqueo
                                ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                            """)
                            print(f"✅ Columna {col} agregada")
                        elif col == 'activo':
                            cursor.execute("""
                                ALTER TABLE ventas_servicioslotbloqueo
                                ADD COLUMN activo BOOLEAN DEFAULT TRUE
                            """)
                            print(f"✅ Columna {col} agregada")

                connection.commit()
                print("\n✅ Todas las columnas necesarias agregadas")
                print("El calendario debería funcionar ahora.")

        else:
            print("\n✅ La columna created_at ya existe")

except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    connection.rollback()

print("\n=== FIN ===")