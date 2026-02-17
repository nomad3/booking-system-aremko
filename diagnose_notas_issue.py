import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

print("=== DIAGNÓSTICO COMPLETO DEL PROBLEMA NOTAS ===\n")

# 1. Verificar el modelo
print("1. MODELO ServicioSlotBloqueo:")
try:
    from ventas.models import ServicioSlotBloqueo
    fields = [f.name for f in ServicioSlotBloqueo._meta.get_fields()]
    print(f"   Campos: {fields}")
    print(f"   ¿Tiene 'notas'? {'✅ SÍ' if 'notas' in fields else '❌ NO'}")
except Exception as e:
    print(f"   Error: {e}")

# 2. Verificar la base de datos
print("\n2. BASE DE DATOS:")
from django.db import connection
cursor = connection.cursor()
cursor.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'ventas_servicioslotbloqueo'
    AND column_name = 'notas'
""")
db_has_notas = cursor.fetchone() is not None
print(f"   ¿Columna 'notas' en BD? {'✅ SÍ' if db_has_notas else '❌ NO'}")

# 3. Verificar el código
print("\n3. CÓDIGO calendario_matriz_view.py:")
try:
    with open('/app/ventas/views/calendario_matriz_view.py', 'r') as f:
        content = f.read()

    # Contar accesos a .notas
    import re
    notas_accesses = re.findall(r'(\w+)\.notas', content)
    print(f"   Accesos a .notas encontrados: {len(notas_accesses)}")

    # Ver línea 452 específicamente
    lines = content.split('\n')
    if len(lines) > 451:
        print(f"   Línea 452: {lines[451].strip()[:80]}...")

except Exception as e:
    print(f"   Error: {e}")

# 4. Diagnóstico
print("\n4. DIAGNÓSTICO:")
if not ('notas' in fields) and db_has_notas:
    print("   ❌ PROBLEMA: La BD tiene 'notas' pero el modelo NO")
    print("   ✅ SOLUCIÓN: Ejecutar 'python add_notas_to_model.py'")
elif 'notas' in fields and db_has_notas:
    print("   ✅ Todo parece estar bien")
    print("   🔄 Intenta reiniciar la aplicación: kill 1")
else:
    print("   ⚠️  Situación inesperada, revisar manualmente")

print("\n=== FIN DIAGNÓSTICO ===")