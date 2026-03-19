#!/usr/bin/env python
"""
Script para crear ServicioBloqueo haciendo bypass de TODAS las validaciones
"""
import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection
from ventas.models import ServicioBloqueo, Servicio
from django.contrib.auth.models import User

print("=== CREAR SERVICIOBLOQUEO CON BYPASS ===\n")

# 1. Obtener datos
servicio = Servicio.objects.filter(activo=True).first()
usuario = User.objects.filter(is_superuser=True).first()
fecha_inicio = date.today() + timedelta(days=7)
fecha_fin = fecha_inicio + timedelta(days=2)

print(f"1. Datos para el bloqueo:")
print(f"   Servicio: {servicio.nombre}")
print(f"   Fechas: {fecha_inicio} al {fecha_fin}")
print(f"   Usuario: {usuario.username}")

# 2. Método 1: Inserción directa en BD
print("\n2. Intentando inserción directa en BD...")
try:
    with connection.cursor() as cursor:
        # Primero, llenar los campos incorrectos con valores por defecto
        cursor.execute("""
            INSERT INTO ventas_serviciobloqueo
            (servicio_id, fecha_inicio, fecha_fin, motivo, activo, creado_en, creado_por_id, fecha, hora_slot)
            VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s, %s)
            RETURNING id
        """, [
            servicio.id,
            fecha_inicio,
            fecha_fin,
            "Creado con bypass de validaciones",
            True,
            usuario.id,
            fecha_inicio,  # fecha = fecha_inicio
            'N/A'         # hora_slot con valor por defecto
        ])

        bloqueo_id = cursor.fetchone()[0]
        print(f"   ✅ ÉXITO: Bloqueo creado con ID: {bloqueo_id}")

        # Verificar
        cursor.execute("""
            SELECT * FROM ventas_serviciobloqueo WHERE id = %s
        """, [bloqueo_id])

        print("\n3. Bloqueo creado exitosamente")
        print("   Ahora deberías verlo en el admin")

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# 3. Método 2: Usando Django pero sin validaciones
print("\n4. Alternativa: Crear con Django sin validaciones...")
try:
    # Temporalmente desactivar el método save
    original_save = ServicioBloqueo.save
    original_clean = ServicioBloqueo.clean

    # Reemplazar con versiones vacías
    ServicioBloqueo.save = lambda self, *args, **kwargs: super(ServicioBloqueo, self).save(*args, **kwargs)
    ServicioBloqueo.clean = lambda self: None

    # Crear el objeto
    bloqueo = ServicioBloqueo(
        servicio=servicio,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        motivo="Test con bypass Django",
        activo=True,
        creado_por=usuario
    )

    # Si tiene campos extra, llenarlos
    if hasattr(bloqueo, 'fecha'):
        bloqueo.fecha = fecha_inicio
    if hasattr(bloqueo, 'hora_slot'):
        bloqueo.hora_slot = 'N/A'

    # Guardar directamente
    bloqueo.save_base(raw=True)
    print(f"   ✅ Creado con Django: ID {bloqueo.id}")

    # Restaurar métodos originales
    ServicioBloqueo.save = original_save
    ServicioBloqueo.clean = original_clean

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== FIN BYPASS ===")