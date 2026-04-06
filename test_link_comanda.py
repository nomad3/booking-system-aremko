#!/usr/bin/env python
"""
Script rápido para probar un link de comanda específico
Uso: python test_link_comanda.py <token>
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Comanda
from django.urls import reverse, resolve

if len(sys.argv) < 2:
    print("❌ Uso: python test_link_comanda.py <token>")
    sys.exit(1)

token = sys.argv[1]

print("="*60)
print(f"PROBANDO TOKEN: {token[:20]}...")
print("="*60)
print()

# 1. Verificar que existe la comanda
try:
    comanda = Comanda.objects.get(token_acceso=token)
    print(f"✅ Comanda encontrada: #{comanda.id}")
    print(f"   Estado: {comanda.estado}")
    print(f"   Reserva: #{comanda.venta_reserva.id if comanda.venta_reserva else 'N/A'}")
    print(f"   Creada por cliente: {comanda.creada_por_cliente}")
except Comanda.DoesNotExist:
    print(f"❌ No existe comanda con token: {token}")
    sys.exit(1)

print()

# 2. Verificar validez del link
if comanda.es_link_valido():
    print(f"✅ Link VÁLIDO hasta: {comanda.fecha_vencimiento_link}")
else:
    print(f"❌ Link EXPIRADO (venció: {comanda.fecha_vencimiento_link})")

print()

# 3. Probar generación de URL
try:
    url_path = reverse('ventas:comanda_cliente', kwargs={'token': token})
    print(f"✅ URL generada: {url_path}")

    # Intentar resolver
    try:
        match = resolve(url_path)
        print(f"✅ URL resuelve a: {match.func.__name__}")
        print(f"   View module: {match.func.__module__}")
    except Exception as e:
        print(f"❌ Error al resolver URL: {e}")

except Exception as e:
    print(f"❌ Error al generar URL: {e}")

print()

# 4. Verificar que la vista existe
try:
    from ventas import views_comandas_cliente
    print(f"✅ Módulo views_comandas_cliente importado")

    if hasattr(views_comandas_cliente, 'comanda_cliente_menu'):
        print(f"✅ Vista comanda_cliente_menu existe")
    else:
        print(f"❌ Vista comanda_cliente_menu NO EXISTE")

except ImportError as e:
    print(f"❌ Error importando views_comandas_cliente: {e}")

print()

# 5. Obtener URL completa
try:
    url_completa = comanda.obtener_url_cliente()
    print(f"URL COMPLETA para copiar:")
    print(f"👉 {url_completa}")
except Exception as e:
    print(f"❌ Error al obtener URL completa: {e}")

print()
print("="*60)
