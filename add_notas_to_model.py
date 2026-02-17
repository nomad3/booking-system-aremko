import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

print("=== AGREGAR CAMPO NOTAS AL MODELO SERVICIOSLOTBLOQUEO ===\n")

# 1. Buscar el modelo en models.py
models_file = '/app/ventas/models.py'

try:
    with open(models_file, 'r') as f:
        lines = f.readlines()

    print("Buscando definición de ServicioSlotBloqueo...")

    # Buscar la clase
    in_class = False
    class_start = -1
    insert_position = -1

    for i, line in enumerate(lines):
        if 'class ServicioSlotBloqueo' in line:
            in_class = True
            class_start = i
            print(f"✅ Encontrada en línea {i+1}")

        elif in_class:
            # Buscar dónde insertar el campo notas
            if 'class Meta:' in line or 'def ' in line:
                # Insertar antes de Meta o métodos
                insert_position = i
                break
            elif line.strip() == '' and i > class_start + 10:
                # O al final de los campos si hay línea en blanco
                insert_position = i
                break

    if insert_position > 0:
        print(f"\nAgregaré el campo 'notas' en la línea {insert_position}")

        respuesta = input("\n¿Agregar campo 'notas' al modelo? (s/n): ")

        if respuesta.lower() == 's':
            # Preparar el campo a insertar
            indent = "    "  # 4 espacios para campos de clase
            new_field = f"{indent}notas = models.TextField(\n"
            new_field += f"{indent}    blank=True,\n"
            new_field += f"{indent}    null=True,\n"
            new_field += f"{indent}    verbose_name='Notas',\n"
            new_field += f"{indent}    help_text='Notas adicionales sobre el bloqueo'\n"
            new_field += f"{indent})\n\n"

            # Insertar el campo
            lines.insert(insert_position, new_field)

            # Escribir el archivo actualizado
            with open(models_file, 'w') as f:
                f.writelines(lines)

            print("\n✅ Campo 'notas' agregado al modelo ServicioSlotBloqueo")
            print("\n⚠️  IMPORTANTE:")
            print("1. El modelo ahora tiene el campo 'notas'")
            print("2. La columna YA existe en la base de datos")
            print("3. NO necesitas ejecutar migraciones")
            print("4. Solo necesitas REINICIAR la aplicación:")
            print("\n   kill 1\n")
            print("5. Espera 60 segundos y prueba el calendario")

    else:
        print("\n❌ No se pudo encontrar dónde insertar el campo")
        print("Puede que el modelo ya tenga el campo o la estructura sea diferente")

except Exception as e:
    print(f"\n❌ Error: {str(e)}")

print("\n=== FIN ===")