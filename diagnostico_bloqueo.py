#!/usr/bin/env python
"""
Script para diagnosticar el error 500 al crear ServicioBloqueo
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.conf import settings
from ventas.models import ServicioBloqueo, Servicio
from django.utils import timezone
from datetime import datetime, timedelta
import traceback

print("=== DIAGNÓSTICO ERROR 500 SERVICIOBLOQUEO ===\n")

# 1. Verificar configuración de email
print("1. Configuración de Email:")
print(f"   EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
print(f"   EMAIL_HOST: {getattr(settings, 'EMAIL_HOST', 'No configurado')}")
print(f"   EMAIL_HOST_USER: {getattr(settings, 'EMAIL_HOST_USER', 'No configurado')}")
print(f"   SendGrid API Key existe: {'SENDGRID_API_KEY' in os.environ}")

# 2. Intentar crear un ServicioBloqueo de prueba
print("\n2. Intentando crear ServicioBloqueo de prueba...")
try:
    # Obtener un servicio para la prueba
    servicio = Servicio.objects.first()
    if not servicio:
        print("   ❌ No hay servicios en la base de datos")
    else:
        print(f"   Servicio seleccionado: {servicio.nombre}")

        # Crear instancia sin guardar
        bloqueo_prueba = ServicioBloqueo(
            servicio=servicio,
            fecha_inicio=timezone.now().date() + timedelta(days=30),
            fecha_fin=timezone.now().date() + timedelta(days=32),
            motivo="Prueba diagnóstico",
            activo=True
        )

        # Intentar validar
        print("   Ejecutando clean()...")
        try:
            bloqueo_prueba.clean()
            print("   ✅ clean() ejecutado sin errores")
        except Exception as e:
            print(f"   ❌ Error en clean(): {str(e)}")
            traceback.print_exc()

        # Intentar full_clean
        print("\n   Ejecutando full_clean()...")
        try:
            bloqueo_prueba.full_clean()
            print("   ✅ full_clean() ejecutado sin errores")
        except Exception as e:
            print(f"   ❌ Error en full_clean(): {str(e)}")
            traceback.print_exc()

        # Intentar guardar
        print("\n   Intentando save()...")
        try:
            bloqueo_prueba.save()
            print(f"   ✅ ServicioBloqueo creado exitosamente con ID: {bloqueo_prueba.id}")
            # Eliminar el de prueba
            bloqueo_prueba.delete()
            print("   ✅ ServicioBloqueo de prueba eliminado")
        except Exception as e:
            print(f"   ❌ Error en save(): {str(e)}")
            traceback.print_exc()

except Exception as e:
    print(f"   ❌ Error general: {str(e)}")
    traceback.print_exc()

# 3. Verificar si hay signals o middleware problemáticos
print("\n3. Verificando signals registrados...")
from django.db.models.signals import post_save, pre_save
from django.dispatch import Signal

# Verificar signals para ServicioBloqueo
for signal in [pre_save, post_save]:
    receivers = signal.receivers
    for receiver in receivers:
        if hasattr(receiver[1], '__self__') and receiver[1].__self__ == ServicioBloqueo:
            print(f"   - Signal {signal} conectado a ServicioBloqueo")

print("\n=== FIN DIAGNÓSTICO ===")