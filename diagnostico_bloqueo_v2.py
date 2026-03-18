#!/usr/bin/env python
"""
Script mejorado para diagnosticar el error en ServicioBloqueo
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import ServicioBloqueo, Servicio
from django.utils import timezone
from datetime import datetime, timedelta

print("=== DIAGNÓSTICO DETALLADO SERVICIOBLOQUEO ===\n")

# 1. Verificar qué modelo estamos usando realmente
print("1. Información del modelo ServicioBloqueo:")
print(f"   Clase: {ServicioBloqueo}")
print(f"   Módulo: {ServicioBloqueo.__module__}")
print(f"   Campos del modelo:")
for field in ServicioBloqueo._meta.get_fields():
    print(f"     - {field.name}: {field.__class__.__name__}")

# 2. Verificar si ServicioBloqueo tiene campo 'fecha'
tiene_fecha = hasattr(ServicioBloqueo, 'fecha')
print(f"\n2. ServicioBloqueo tiene campo 'fecha': {tiene_fecha}")

# 3. Probar el método servicio_bloqueado_en_fecha directamente
print("\n3. Probando método servicio_bloqueado_en_fecha:")
try:
    servicio = Servicio.objects.first()
    if servicio:
        fecha_prueba = timezone.now().date()
        print(f"   Servicio: {servicio.nombre} (ID: {servicio.id})")
        print(f"   Fecha: {fecha_prueba}")
        resultado = ServicioBloqueo.servicio_bloqueado_en_fecha(servicio.id, fecha_prueba)
        print(f"   Resultado: {resultado}")
except Exception as e:
    print(f"   ❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()

# 4. Ver el código del método clean
print("\n4. Código del método clean de ServicioBloqueo:")
import inspect
if hasattr(ServicioBloqueo, 'clean'):
    print(inspect.getsource(ServicioBloqueo.clean))
else:
    print("   ServicioBloqueo no tiene método clean definido")

print("\n=== FIN DIAGNÓSTICO ===")