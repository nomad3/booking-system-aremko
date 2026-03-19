#!/usr/bin/env python
"""
Script para debuggear el error al crear ServicioBloqueo
Simula lo que hace el admin paso a paso
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import ServicioBloqueo, Servicio
from django.contrib.auth.models import User
from datetime import date, timedelta
import traceback

print("=== DEBUG CREAR SERVICIOBLOQUEO ===\n")

# 1. Obtener datos necesarios
servicio = Servicio.objects.filter(activo=True).first()
usuario = User.objects.filter(is_superuser=True).first()

if not servicio:
    print("❌ No hay servicios activos")
    exit(1)

print(f"1. Datos de prueba:")
print(f"   Servicio: {servicio.nombre} (ID: {servicio.id})")
print(f"   Usuario: {usuario.username if usuario else 'No hay superusuario'}")

# 2. Crear instancia sin guardar
print("\n2. Creando instancia de ServicioBloqueo...")
fecha_inicio = date.today() + timedelta(days=30)
fecha_fin = fecha_inicio + timedelta(days=2)

try:
    bloqueo = ServicioBloqueo(
        servicio=servicio,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        motivo="Test debug",
        activo=True,
        notas="Creado desde script debug",
        creado_por=usuario
    )
    print("   ✅ Instancia creada (sin guardar)")

    # Ver qué campos tiene realmente
    print("\n3. Campos de la instancia:")
    for field in bloqueo._meta.get_fields():
        if hasattr(bloqueo, field.name):
            valor = getattr(bloqueo, field.name, 'NO TIENE')
            print(f"   - {field.name}: {valor}")

except Exception as e:
    print(f"   ❌ Error creando instancia: {e}")
    traceback.print_exc()
    exit(1)

# 3. Probar clean()
print("\n4. Ejecutando clean()...")
try:
    # Verificar si tiene método clean
    if hasattr(bloqueo, 'clean'):
        print("   Tiene método clean(), ejecutando...")
        # Imprimir el código del método clean
        import inspect
        print("\n   Código del método clean:")
        print(inspect.getsource(bloqueo.clean))

        bloqueo.clean()
        print("   ✅ clean() exitoso")
    else:
        print("   No tiene método clean()")
except Exception as e:
    print(f"   ❌ Error en clean(): {e}")
    traceback.print_exc()

# 4. Probar full_clean()
print("\n5. Ejecutando full_clean()...")
try:
    bloqueo.full_clean()
    print("   ✅ full_clean() exitoso")
except Exception as e:
    print(f"   ❌ Error en full_clean(): {e}")
    print("\n   Detalles del error:")
    if hasattr(e, 'message_dict'):
        for campo, errores in e.message_dict.items():
            print(f"   - {campo}: {errores}")
    traceback.print_exc()

# 5. Intentar guardar
print("\n6. Intentando save()...")
try:
    # Establecer valores para campos problemáticos si existen
    if hasattr(bloqueo, 'fecha') and not bloqueo.fecha:
        bloqueo.fecha = bloqueo.fecha_inicio
        print("   Estableciendo fecha = fecha_inicio")

    if hasattr(bloqueo, 'created_at') and not bloqueo.created_at:
        from django.utils import timezone
        bloqueo.created_at = timezone.now()
        print("   Estableciendo created_at = now")

    if hasattr(bloqueo, 'updated_at') and not bloqueo.updated_at:
        from django.utils import timezone
        bloqueo.updated_at = timezone.now()
        print("   Estableciendo updated_at = now")

    bloqueo.save()
    print(f"   ✅ Guardado exitosamente con ID: {bloqueo.id}")

    # Eliminar el de prueba
    bloqueo.delete()
    print("   ✅ Eliminado el registro de prueba")

except Exception as e:
    print(f"   ❌ Error en save(): {e}")
    print(f"   Tipo de error: {type(e).__name__}")
    traceback.print_exc()

print("\n=== FIN DEBUG ===")