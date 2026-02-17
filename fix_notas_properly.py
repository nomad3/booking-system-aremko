import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

print("=== ARREGLAR ACCESO A NOTAS CORRECTAMENTE ===\n")

try:
    # Leer el archivo
    with open('/app/ventas/views/calendario_matriz_view.py', 'r') as f:
        lines = f.readlines()

    print(f"Archivo tiene {len(lines)} líneas")

    # Buscar y reemplazar la línea problemática
    cambios = 0
    for i, line in enumerate(lines):
        if 'bloqueo_slot.notas' in line and 'getattr' not in line:
            print(f"\nEncontrada línea {i+1}: {line.strip()}")

            # Reemplazar la línea completa
            if "'notas_bloqueo': bloqueo_slot.notas if bloqueo_slot.notas else None," in line:
                # Mantener la indentación
                indent = line[:len(line) - len(line.lstrip())]
                new_line = f"{indent}'notas_bloqueo': getattr(bloqueo_slot, 'notas', None),\n"
                lines[i] = new_line
                print(f"Reemplazada por: {new_line.strip()}")
                cambios += 1
            else:
                # Para otros casos, reemplazar bloqueo_slot.notas por getattr
                new_line = line.replace('bloqueo_slot.notas', "getattr(bloqueo_slot, 'notas', '')")
                lines[i] = new_line
                print(f"Reemplazada por: {new_line.strip()}")
                cambios += 1

    if cambios > 0:
        # Escribir el archivo modificado
        with open('/app/ventas/views/calendario_matriz_view.py', 'w') as f:
            f.writelines(lines)

        print(f"\n✅ Se realizaron {cambios} cambios")
        print("El archivo fue actualizado exitosamente")

        # Verificar el cambio
        with open('/app/ventas/views/calendario_matriz_view.py', 'r') as f:
            lines_new = f.readlines()

        if len(lines_new) >= 452:
            print(f"\nLínea 452 ahora dice:")
            print(f"  {lines_new[451].strip()}")

        print("\n⚠️  IMPORTANTE: Debes reiniciar la aplicación")
        print("Ejecuta: kill 1")
    else:
        print("\n⚠️  No se encontraron líneas para cambiar")
        print("El archivo puede ya estar parcheado o el problema está en otro lugar")

except Exception as e:
    print(f"\n❌ Error: {str(e)}")

print("\n=== FIN ===")