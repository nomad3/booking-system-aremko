import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

print("=== ARREGLAR PROBLEMA DEL CALENDARIO ===\n")

# 1. Ver el problema específico
print("1. Buscando el problema en calendario_matriz_view.py:")
try:
    with open('/app/ventas/views/calendario_matriz_view.py', 'r') as f:
        lines = f.readlines()

    # Buscar líneas con ServicioBloqueo.objects
    for i, line in enumerate(lines):
        if 'ServicioBloqueo.objects' in line and 'hora_slot' in line:
            print(f"\n   Línea {i+1}: {line.strip()}")
            # Mostrar contexto
            for j in range(max(0, i-2), min(i+3, len(lines))):
                print(f"   {j+1}: {lines[j].rstrip()}")
            break

except Exception as e:
    print(f"   Error: {e}")

# 2. Ver cómo está definido ServicioBloqueo
print("\n2. Definición actual de ServicioBloqueo en models.py:")
try:
    with open('/app/ventas/models.py', 'r') as f:
        lines = f.readlines()

    in_class = False
    for i, line in enumerate(lines):
        if 'class ServicioBloqueo' in line:
            in_class = True
            start = i
        elif in_class and line.startswith('class '):
            # Mostrar solo las primeras 30 líneas de la clase
            for j in range(start, min(start+30, i)):
                print(f"   {lines[j].rstrip()}")
            break

except Exception as e:
    print(f"   Error: {e}")

# 3. Identificar el problema exacto
print("\n3. PROBLEMA IDENTIFICADO:")
print("   El calendario está buscando 'hora_slot' en ServicioBloqueo")
print("   pero 'hora_slot' solo debe existir en ServicioSlotBloqueo")

print("\n4. SOLUCIONES POSIBLES:")
print("   a) Modificar calendario_matriz_view.py para usar el modelo correcto")
print("   b) Agregar columna hora_slot a ServicioBloqueo (temporal)")

respuesta = input("\n¿Aplicar solución temporal agregando columna hora_slot? (s/n): ")

if respuesta.lower() == 's':
    from django.db import connection
    cursor = connection.cursor()

    try:
        # Verificar si ya existe
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'ventas_serviciobloqueo'
            AND column_name = 'hora_slot'
        """)

        if not cursor.fetchone():
            print("\nAgregando columna hora_slot...")
            cursor.execute("""
                ALTER TABLE ventas_serviciobloqueo
                ADD COLUMN hora_slot VARCHAR(10)
            """)
            connection.commit()
            print("✅ Columna agregada")
        else:
            print("\n✅ La columna hora_slot ya existe")

        print("\nEl calendario debería funcionar ahora.")
        print("NOTA: Esta es una solución temporal.")
        print("El código necesita ser actualizado para usar los modelos correctos.")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        connection.rollback()
else:
    print("\nSolución cancelada.")

print("\n=== FIN ===")