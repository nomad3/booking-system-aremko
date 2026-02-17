import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

print("=== DIAGNÓSTICO CONFUSIÓN DE MODELOS ===\n")

cursor = connection.cursor()

# 1. Verificar tablas
print("1. Verificando tablas existentes:")
for tabla in ['ventas_serviciobloqueo', 'ventas_servicioslotbloqueo']:
    cursor.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{tabla}')")
    existe = cursor.fetchone()[0]
    print(f"   {tabla}: {'✅ Existe' if existe else '❌ No existe'}")

# 2. Columnas de ServicioBloqueo
print("\n2. Columnas en ventas_serviciobloqueo:")
cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'ventas_serviciobloqueo'")
columnas = [col[0] for col in cursor.fetchall()]
print(f"   {columnas}")
print(f"   ¿Tiene hora_slot? {'✅ SÍ' if 'hora_slot' in columnas else '❌ NO'}")

# 3. Columnas de ServicioSlotBloqueo (si existe)
cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ventas_servicioslotbloqueo')")
if cursor.fetchone()[0]:
    print("\n3. Columnas en ventas_servicioslotbloqueo:")
    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'ventas_servicioslotbloqueo'")
    columnas_slot = [col[0] for col in cursor.fetchall()]
    print(f"   {columnas_slot}")

# 4. Ver qué esperan los modelos
print("\n4. Verificando modelos:")
try:
    from ventas.models import ServicioBloqueo, ServicioSlotBloqueo

    print("\n   ServicioBloqueo campos:")
    campos_bloqueo = [f.name for f in ServicioBloqueo._meta.get_fields()]
    print(f"   {campos_bloqueo}")

    print("\n   ServicioSlotBloqueo campos:")
    campos_slot = [f.name for f in ServicioSlotBloqueo._meta.get_fields()]
    print(f"   {campos_slot}")

except Exception as e:
    print(f"   ❌ Error al importar modelos: {str(e)}")

print("\n=== ANÁLISIS ===")
print("\nParece que el código está confundiendo ServicioBloqueo con ServicioSlotBloqueo.")
print("El calendario está buscando 'hora_slot' en la tabla equivocada.")

print("\n=== FIN DIAGNÓSTICO ===")