import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

print("=== VERIFICAR CÓDIGO DEL CALENDARIO ===\n")

# Buscar archivos relacionados con el calendario
print("1. Buscando archivos del calendario:")
import subprocess
try:
    result = subprocess.run(['find', '/app', '-name', '*calendario*', '-type', 'f'],
                          capture_output=True, text=True)
    archivos = result.stdout.strip().split('\n')
    for archivo in archivos[:10]:  # Primeros 10
        if archivo:
            print(f"   - {archivo}")
except Exception as e:
    print(f"   Error: {e}")

# Ver el error específico
print("\n2. El error menciona:")
print("   - calendario_seleccion_view.py línea 77")
print("   - generar_matriz_disponibilidad")

# Verificar qué modelo se está usando
print("\n3. Verificando imports en modelos:")
try:
    # Leer parte del archivo models.py
    with open('/app/ventas/models.py', 'r') as f:
        lines = f.readlines()

    # Buscar definiciones de ServicioBloqueo
    in_serviciobloqueo = False
    line_count = 0

    for i, line in enumerate(lines):
        if 'class ServicioBloqueo' in line:
            print(f"\n   Encontrado ServicioBloqueo en línea {i+1}:")
            # Mostrar las siguientes 20 líneas
            for j in range(i, min(i+20, len(lines))):
                print(f"   {lines[j].rstrip()}")
            break

except Exception as e:
    print(f"   Error leyendo models.py: {e}")

print("\n=== PROBLEMA IDENTIFICADO ===")
print("\nEl calendario está intentando usar ServicioBloqueo como si fuera ServicioSlotBloqueo.")
print("Necesita usar la tabla correcta para cada tipo de bloqueo.")

print("\n=== FIN ===")