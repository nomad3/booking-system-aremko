import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

print("=== INVESTIGAR PROBLEMA CON NOTAS EN SERVICIOSLOTBLOQUEO ===\n")

# 1. Verificar si la columna existe en la BD
cursor = connection.cursor()
cursor.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'ventas_servicioslotbloqueo'
    AND column_name = 'notas'
""")
existe_en_bd = cursor.fetchone() is not None

print(f"1. ¿Columna 'notas' existe en la BD? {'✅ SÍ' if existe_en_bd else '❌ NO'}")

# 2. Verificar el modelo
print("\n2. Verificando el modelo ServicioSlotBloqueo...")
try:
    from ventas.models import ServicioSlotBloqueo

    # Verificar campos del modelo
    campos = [f.name for f in ServicioSlotBloqueo._meta.get_fields()]
    tiene_notas_modelo = 'notas' in campos

    print(f"   Campos del modelo: {campos}")
    print(f"   ¿Modelo tiene 'notas'? {'✅ SÍ' if tiene_notas_modelo else '❌ NO'}")

    # Si existe en BD pero no en modelo, es problema de sincronización
    if existe_en_bd and not tiene_notas_modelo:
        print("\n⚠️  PROBLEMA: La columna existe en la BD pero no en el modelo Django")
        print("   Esto puede pasar cuando se agregaron columnas manualmente sin actualizar models.py")

except Exception as e:
    print(f"   ❌ Error al importar modelo: {str(e)}")

# 3. Ver cómo está usando 'notas' el calendario
print("\n3. Buscando uso de 'notas' en calendario_matriz_view.py...")
try:
    with open('/app/ventas/views/calendario_matriz_view.py', 'r') as f:
        lines = f.readlines()

    # Buscar línea 452 mencionada en el error
    if len(lines) >= 452:
        print(f"\n   Línea 452: {lines[451].strip()}")
        # Mostrar contexto
        for i in range(max(0, 449), min(455, len(lines))):
            print(f"   {i+1}: {lines[i].rstrip()}")

except Exception as e:
    print(f"   Error leyendo archivo: {e}")

# 4. Solución propuesta
print("\n4. SOLUCIONES POSIBLES:")
print("   a) Agregar campo 'notas' al modelo (requiere modificar models.py)")
print("   b) Comentar/eliminar el acceso a 'notas' en el calendario")
print("   c) Usar getattr con valor por defecto")

respuesta = input("\n¿Aplicar solución temporal usando getattr? (s/n): ")

if respuesta.lower() == 's':
    print("\nCreando parche temporal...")

    # Buscar y reemplazar el acceso a .notas
    try:
        with open('/app/ventas/views/calendario_matriz_view.py', 'r') as f:
            content = f.read()

        # Buscar patrones como bloqueo_slot.notas
        import re
        original_pattern = r'(bloqueo_slot\.notas)'
        replacement = r'getattr(bloqueo_slot, "notas", "")'

        new_content = re.sub(original_pattern, replacement, content)

        if new_content != content:
            with open('/app/ventas/views/calendario_matriz_view.py', 'w') as f:
                f.write(new_content)
            print("✅ Archivo parcheado. El acceso a 'notas' ahora usa getattr()")
            print("   Si el campo no existe, retornará cadena vacía")
        else:
            print("⚠️  No se encontró el patrón bloqueo_slot.notas")
            print("   El problema puede estar en otra parte del código")

    except Exception as e:
        print(f"❌ Error al parchear: {str(e)}")

print("\n=== FIN ===")