import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

print("=== VERIFICAR Y ARREGLAR TODOS LOS ACCESOS A NOTAS ===\n")

archivo = '/app/ventas/views/calendario_matriz_view.py'

try:
    # Leer el archivo
    with open(archivo, 'r') as f:
        content = f.read()
        lines = content.split('\n')

    print(f"Archivo tiene {len(lines)} líneas\n")

    # Buscar TODOS los accesos a .notas
    import re
    pattern = r'(\w+)\.notas\b'
    matches = list(re.finditer(pattern, content))

    if matches:
        print(f"Encontrados {len(matches)} accesos a .notas:\n")

        for match in matches:
            # Encontrar número de línea
            line_start = content.rfind('\n', 0, match.start()) + 1
            line_num = content.count('\n', 0, line_start) + 1
            line_text = content[line_start:content.find('\n', match.start())]

            print(f"Línea {line_num}: {line_text.strip()}")

        respuesta = input("\n¿Reemplazar TODOS los accesos a .notas con getattr? (s/n): ")

        if respuesta.lower() == 's':
            # Hacer los reemplazos
            new_content = content

            # Reemplazar patrones específicos
            replacements = [
                # Patrón: objeto.notas if objeto.notas else X
                (r'(\w+)\.notas if \1\.notas else ([^,\n]+)',
                 r"getattr(\1, 'notas', \2)"),

                # Patrón: objeto.notas (simple)
                (r'(\w+)\.notas\b(?! if)',
                 r"getattr(\1, 'notas', '')"),
            ]

            for pattern, replacement in replacements:
                new_content = re.sub(pattern, replacement, new_content)

            # Escribir el archivo modificado
            with open(archivo, 'w') as f:
                f.write(new_content)

            print("\n✅ Archivo actualizado exitosamente")

            # Verificar los cambios
            with open(archivo, 'r') as f:
                verify_content = f.read()

            remaining = len(re.findall(r'(\w+)\.notas\b', verify_content))
            if remaining == 0:
                print("✅ Todos los accesos a .notas han sido reemplazados")
            else:
                print(f"⚠️  Aún quedan {remaining} accesos a .notas")

            print("\n⚠️  IMPORTANTE: REINICIA LA APLICACIÓN")
            print("Ejecuta uno de estos comandos:")
            print("  kill 1")
            print("  pkill -f python")
            print("  pkill gunicorn")

    else:
        print("✅ No se encontraron accesos directos a .notas")
        print("El archivo ya está parcheado o el error viene de otro lugar")

except Exception as e:
    print(f"\n❌ Error: {str(e)}")

print("\n=== FIN ===")