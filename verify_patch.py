import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

print("=== VERIFICAR PARCHE APLICADO ===\n")

# Buscar la línea 452 en calendario_matriz_view.py
try:
    with open('/app/ventas/views/calendario_matriz_view.py', 'r') as f:
        lines = f.readlines()

    if len(lines) >= 452:
        line_452 = lines[451].strip()  # Índice 451 = línea 452
        print(f"Línea 452 actual:")
        print(f"  {line_452}")

        if "getattr(" in line_452:
            print("\n✅ El parche SÍ se aplicó correctamente")
            print("   La línea usa getattr() como esperábamos")
            print("\n⚠️  NECESITAS REINICIAR LA APLICACIÓN")
            print("   Ejecuta: kill 1")
        else:
            print("\n❌ El parche NO se aplicó")
            print("   La línea todavía usa acceso directo .notas")

except Exception as e:
    print(f"Error al verificar: {str(e)}")

print("\n=== FIN ===")