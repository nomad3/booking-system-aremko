import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

print("=== AGREGAR COLUMNA NOTAS SI FALTA ===\n")

cursor = connection.cursor()

# Verificar si ya existe
cursor.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'ventas_servicioslotbloqueo'
    AND column_name = 'notas'
""")

if cursor.fetchone():
    print("✅ La columna 'notas' ya existe en ventas_servicioslotbloqueo")
else:
    print("❌ Falta la columna 'notas'")
    respuesta = input("\n¿Agregar columna notas? (s/n): ")

    if respuesta.lower() == 's':
        try:
            cursor.execute("""
                ALTER TABLE ventas_servicioslotbloqueo
                ADD COLUMN notas TEXT DEFAULT ''
            """)
            connection.commit()
            print("\n✅ Columna 'notas' agregada exitosamente")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            connection.rollback()

print("\n=== FIN ===")