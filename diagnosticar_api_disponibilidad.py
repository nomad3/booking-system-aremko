#!/usr/bin/env python
"""
Script para diagnosticar el problema de la API de disponibilidad.
Ejecutar en Render Shell: python diagnosticar_api_disponibilidad.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import RequestFactory, Client
from django.contrib.auth import get_user_model
from ventas.models import Servicio
from ventas.views.availability_views import check_slot_availability

User = get_user_model()

print("=" * 80)
print("🔍 DIAGNÓSTICO: API de Verificación de Disponibilidad")
print("=" * 80)

# TEST 1: Verificar que existe un servicio
print("\n📋 TEST 1: Verificar Servicio")
print("-" * 80)
try:
    servicio = Servicio.objects.first()
    if servicio:
        print(f"✅ Servicio encontrado: {servicio.nombre} (ID: {servicio.id})")
    else:
        print("❌ No hay servicios en la BD")
        sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# TEST 2: Simular request público (sin autenticación)
print("\n📋 TEST 2: Request PÚBLICO (como cliente sin login)")
print("-" * 80)
try:
    factory = RequestFactory()
    # Simular GET request sin usuario autenticado
    request = factory.get(
        f'/check-availability/?servicio_id={servicio.id}&fecha=2026-02-16&hora=14:00'
    )
    # NO asignar usuario (simular request anónimo)
    request.user = None

    print(f"✅ Request creado (anónimo)")
    print(f"   URL simulada: /check-availability/")
    print(f"   Parámetros: servicio_id={servicio.id}, fecha=2026-02-16, hora=14:00")

    # Ejecutar la vista
    response = check_slot_availability(request)

    print(f"\n✅ Vista ejecutada correctamente")
    print(f"   Status code: {response.status_code}")
    print(f"   Content-Type: {response.get('Content-Type', 'N/A')}")

    # Parsear respuesta JSON
    import json
    content = json.loads(response.content.decode('utf-8'))
    print(f"   Respuesta JSON: {content}")

    if response.status_code == 200:
        print(f"\n   ✅ API funciona correctamente para usuarios anónimos")
    else:
        print(f"\n   ❌ Status code inesperado: {response.status_code}")

except Exception as e:
    print(f"❌ Error al ejecutar vista: {e}")
    import traceback
    traceback.print_exc()

# TEST 3: Request con usuario autenticado (admin)
print("\n📋 TEST 3: Request AUTENTICADO (como admin)")
print("-" * 80)
try:
    user = User.objects.filter(is_superuser=True).first()
    if not user:
        user = User.objects.filter(is_staff=True).first()

    if user:
        request = factory.get(
            f'/check-availability/?servicio_id={servicio.id}&fecha=2026-02-16&hora=14:00'
        )
        request.user = user

        print(f"✅ Request creado con usuario: {user.username}")

        response = check_slot_availability(request)

        print(f"✅ Vista ejecutada")
        print(f"   Status code: {response.status_code}")

        content = json.loads(response.content.decode('utf-8'))
        print(f"   Respuesta JSON: {content}")
    else:
        print("⚠️  No hay usuarios staff/admin para probar")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# TEST 4: Usar Django Test Client (simula navegador)
print("\n📋 TEST 4: Test Client (simula navegador real)")
print("-" * 80)
try:
    client = Client()

    # Sin login (usuario anónimo)
    url = f'/ventas/check-availability/?servicio_id={servicio.id}&fecha=2026-02-16&hora=14:00'
    print(f"   URL completa: {url}")

    response = client.get(url)

    print(f"✅ Request ejecutado")
    print(f"   Status code: {response.status_code}")

    if response.status_code == 200:
        content = json.loads(response.content.decode('utf-8'))
        print(f"   Respuesta: {content}")
        print(f"\n   ✅ API accesible desde navegador sin login")
    elif response.status_code == 302:
        print(f"   ❌ Redirección detectada (probablemente a login)")
        print(f"   Location: {response.get('Location', 'N/A')}")
        print(f"\n   🚨 PROBLEMA: La vista requiere autenticación")
    elif response.status_code == 403:
        print(f"   ❌ Forbidden - La vista bloquea acceso anónimo")
        print(f"\n   🚨 PROBLEMA: Permisos incorrectos")
    elif response.status_code >= 500:
        print(f"   ❌ Error 500 - Excepción en el servidor")
        print(f"   Response: {response.content.decode('utf-8')[:500]}")
        print(f"\n   🚨 PROBLEMA: Error interno del servidor")
    else:
        print(f"   ❌ Status inesperado: {response.status_code}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# TEST 5: Verificar middleware que pueda estar bloqueando
print("\n📋 TEST 5: Verificar Middleware de Autenticación")
print("-" * 80)
try:
    from django.conf import settings

    print("   Middleware configurado:")
    for idx, mw in enumerate(settings.MIDDLEWARE, 1):
        print(f"   {idx}. {mw}")

    # Buscar middleware problemático
    auth_middleware = [mw for mw in settings.MIDDLEWARE if 'Auth' in mw or 'Login' in mw]
    if auth_middleware:
        print(f"\n   ⚠️  Middleware de autenticación detectado:")
        for mw in auth_middleware:
            print(f"      - {mw}")
        print(f"   Esto podría estar bloqueando acceso anónimo si está mal configurado")

except Exception as e:
    print(f"❌ Error: {e}")

# RESUMEN
print("\n" + "=" * 80)
print("📊 RESUMEN")
print("=" * 80)
print("""
Si el TEST 2 o TEST 3 pasaron pero el TEST 4 falló con 302/403:
→ El problema es de MIDDLEWARE o decorador global bloqueando

Si todos los tests fallan:
→ El problema está en la vista misma (lógica o imports)

Si TEST 4 da 500:
→ Hay una excepción no capturada en la vista

Si TEST 4 da 200 aquí pero falla en navegador:
→ El problema es de CORS, CSP, o staticfiles

Próximos pasos:
- Revisar logs de Render durante request del navegador
- Verificar consola del navegador (F12 → Console y Network)
- Verificar que la URL en el navegador sea correcta
""")

print("\n✅ Diagnóstico completado")
