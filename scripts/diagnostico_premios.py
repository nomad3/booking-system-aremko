#!/usr/bin/env python
"""
Script de diagnóstico para investigar por qué no se envían emails de premios
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.utils import timezone
from ventas.models import ClientePremio
from datetime import timedelta

print("=" * 80)
print("🔍 DIAGNÓSTICO: Premios Aprobados No Enviados")
print("=" * 80)
print()

# 1. Verificar premios aprobados
print("📋 PASO 1: Premios con estado='aprobado'")
print("-" * 80)

premios_aprobados = ClientePremio.objects.filter(
    estado='aprobado'
).select_related('cliente', 'premio').order_by('-fecha_aprobacion')

print(f"Total premios aprobados: {premios_aprobados.count()}")
print()

if premios_aprobados.exists():
    print("Detalles de premios aprobados:")
    print()
    for i, p in enumerate(premios_aprobados[:10], 1):
        print(f"{i}. ID: {p.id}")
        print(f"   Cliente: {p.cliente.nombre}")
        print(f"   Email: {p.cliente.email}")
        print(f"   Premio: {p.premio.nombre}")
        print(f"   Estado: {p.estado}")
        print(f"   Fecha aprobación: {p.fecha_aprobacion}")
        print(f"   Fecha enviado: {p.fecha_enviado or 'NO ENVIADO'}")
        print()
else:
    print("⚠️  NO hay premios con estado='aprobado'")
    print()

# 2. Verificar premios aprobados RECIENTEMENTE (últimas 24 horas)
print()
print("📋 PASO 2: Premios aprobados en las últimas 24 horas")
print("-" * 80)

hace_24h = timezone.now() - timedelta(hours=24)
premios_recientes = ClientePremio.objects.filter(
    fecha_aprobacion__gte=hace_24h
).select_related('cliente', 'premio').order_by('-fecha_aprobacion')

print(f"Total premios aprobados hoy: {premios_recientes.count()}")
print()

if premios_recientes.exists():
    print("Detalles:")
    print()
    for i, p in enumerate(premios_recientes, 1):
        print(f"{i}. ID: {p.id}")
        print(f"   Cliente: {p.cliente.nombre}")
        print(f"   Email: {p.cliente.email}")
        print(f"   Premio: {p.premio.nombre}")
        print(f"   Estado: {p.estado}")
        print(f"   Fecha aprobación: {p.fecha_aprobacion}")
        print(f"   Fecha enviado: {p.fecha_enviado or 'NO ENVIADO'}")
        print()
else:
    print("⚠️  NO hay premios aprobados en las últimas 24 horas")
    print()

# 3. Ver todos los estados de premios
print()
print("📋 PASO 3: Resumen de premios por estado")
print("-" * 80)

from django.db.models import Count

estados = ClientePremio.objects.values('estado').annotate(
    total=Count('id')
).order_by('-total')

for estado in estados:
    print(f"{estado['estado']:<30} {estado['total']:>10,}")

print()

# 4. Verificar premios que DEBERÍAN ser aprobados pero están en otro estado
print()
print("📋 PASO 4: Premios pendientes de aprobación")
print("-" * 80)

pendientes = ClientePremio.objects.filter(
    estado='pendiente_aprobacion'
).select_related('cliente', 'premio').order_by('-fecha_ganado')[:5]

print(f"Total pendientes de aprobación: {pendientes.count()}")
print()

if pendientes.exists():
    print("Últimos 5 pendientes:")
    print()
    for i, p in enumerate(pendientes, 1):
        print(f"{i}. ID: {p.id}")
        print(f"   Cliente: {p.cliente.nombre}")
        print(f"   Premio: {p.premio.nombre}")
        print(f"   Fecha ganado: {p.fecha_ganado}")
        print()

# 5. Verificar premios enviados recientemente
print()
print("📋 PASO 5: Premios enviados recientemente (últimas 24h)")
print("-" * 80)

enviados_recientes = ClientePremio.objects.filter(
    estado='enviado',
    fecha_enviado__gte=hace_24h
).select_related('cliente', 'premio').order_by('-fecha_enviado')

print(f"Total enviados en las últimas 24 horas: {enviados_recientes.count()}")
print()

if enviados_recientes.exists():
    print("Detalles:")
    print()
    for i, p in enumerate(enviados_recientes, 1):
        print(f"{i}. ID: {p.id}")
        print(f"   Cliente: {p.cliente.nombre}")
        print(f"   Email: {p.cliente.email}")
        print(f"   Premio: {p.premio.nombre}")
        print(f"   Fecha enviado: {p.fecha_enviado}")
        print()

# 6. Verificar configuración de email
print()
print("📋 PASO 6: Configuración de Email")
print("-" * 80)

from django.conf import settings

print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
print(f"EMAIL_PORT: {settings.EMAIL_PORT}")
print(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
print(f"EMAIL_HOST_USER: {'***' + settings.EMAIL_HOST_USER[-20:] if settings.EMAIL_HOST_USER else 'NO CONFIGURADO'}")
print(f"EMAIL_HOST_PASSWORD: {'***' if settings.EMAIL_HOST_PASSWORD else 'NO CONFIGURADO'}")
print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
print()

# 7. Probar envío manual (SOLO SI HAY PREMIOS APROBADOS)
if premios_aprobados.exists():
    print()
    print("=" * 80)
    print("💡 SUGERENCIA")
    print("=" * 80)
    print()
    print("Para probar el envío manual de un premio, ejecuta:")
    print()
    primer_premio = premios_aprobados.first()
    print(f"python manage.py shell")
    print(f">>> from ventas.services.email_premio_service import EmailPremioService")
    print(f">>> resultado = EmailPremioService.enviar_premio({primer_premio.id}, force=True)")
    print(f">>> print(resultado)")
    print()

print("=" * 80)
print("✅ DIAGNÓSTICO COMPLETADO")
print("=" * 80)
