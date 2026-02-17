import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

print("=== DIAGNÓSTICO SERVICIOBLOQUEO ===\n")

cursor = connection.cursor()

# 1. Verificar si la tabla existe
cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ventas_serviciobloqueo')")
existe = cursor.fetchone()[0]
print(f"1. Tabla ventas_serviciobloqueo existe: {'✅ SÍ' if existe else '❌ NO'}")

if existe:
    # 2. Ver columnas de la tabla
    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'ventas_serviciobloqueo'")
    columnas = [col[0] for col in cursor.fetchall()]
    print(f"\n2. Columnas en la tabla: {columnas}")

    # 3. Verificar columna fecha específicamente
    tiene_fecha = 'fecha' in columnas
    print(f"\n3. Tiene columna 'fecha': {'✅ SÍ' if tiene_fecha else '❌ NO'}")

    # 4. Ver qué columnas de fecha existen
    columnas_fecha = [c for c in columnas if 'fecha' in c]
    print(f"\n4. Columnas relacionadas con fecha: {columnas_fecha}")

# 5. Verificar el modelo
print("\n5. Verificando modelo ServicioBloqueo...")
try:
    from ventas.models import ServicioBloqueo
    # Ver campos del modelo
    fields = [f.name for f in ServicioBloqueo._meta.get_fields()]
    print(f"   Campos en el modelo: {fields}")

    # Verificar si tiene fecha
    modelo_tiene_fecha = 'fecha' in fields
    print(f"   Modelo espera campo 'fecha': {'✅ SÍ' if modelo_tiene_fecha else '❌ NO'}")

except Exception as e:
    print(f"   ❌ Error al importar modelo: {str(e)}")

print("\n=== SOLUCIÓN PROPUESTA ===")
if existe and not tiene_fecha and 'fecha_inicio' in columnas:
    print("\nLa tabla tiene 'fecha_inicio' pero el código busca 'fecha'.")
    print("Ejecuta este SQL para arreglar temporalmente:")
    print("ALTER TABLE ventas_serviciobloqueo ADD COLUMN fecha DATE;")
    print("UPDATE ventas_serviciobloqueo SET fecha = fecha_inicio;")
elif not existe:
    print("\nLa tabla no existe. Necesitas ejecutar las migraciones.")

print("\n=== FIN DIAGNÓSTICO ===")