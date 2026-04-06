#!/usr/bin/env python
"""
Script para hacer petición HTTP real a la URL de comanda
Uso: python test_http_comanda.py <token>
"""
import sys
import requests

if len(sys.argv) < 2:
    print("❌ Uso: python test_http_comanda.py <token>")
    sys.exit(1)

token = sys.argv[1]

# Probar desde localhost (dentro del servidor)
url_local = f'http://localhost:8000/ventas/comanda-cliente/{token}/'
url_public = f'https://aremko-booking-system.onrender.com/ventas/comanda-cliente/{token}/'

print("="*70)
print("PROBANDO PETICIÓN HTTP REAL")
print("="*70)
print()

# Probar localhost
print("1. Probando desde localhost (puerto 8000)...")
try:
    response = requests.get(url_local, timeout=10)
    print(f"   Status Code: {response.status_code}")
    print(f"   Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    print(f"   Content-Length: {len(response.content)} bytes")

    if response.status_code == 200:
        print("   ✅ Respuesta exitosa desde localhost")
        if 'Aremko Spa' in response.text:
            print("   ✅ Contenido correcto (contiene 'Aremko Spa')")
    elif response.status_code == 404:
        print("   ❌ 404 Not Found desde localhost")
        print(f"   Contenido: {response.text[:200]}")
    else:
        print(f"   ⚠️ Status inesperado: {response.status_code}")

except requests.exceptions.ConnectionError:
    print("   ⚠️ No se pudo conectar a localhost:8000")
    print("   (El servidor puede estar corriendo en otro puerto)")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Probar URL pública
print("2. Probando URL pública...")
try:
    response = requests.get(url_public, timeout=30)
    print(f"   Status Code: {response.status_code}")
    print(f"   Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    print(f"   Content-Length: {len(response.content)} bytes")

    if response.status_code == 200:
        print("   ✅ Respuesta exitosa desde URL pública")
        if 'Aremko Spa' in response.text:
            print("   ✅ Contenido correcto (contiene 'Aremko Spa')")
    elif response.status_code == 404:
        print("   ❌ 404 Not Found desde URL pública")
        print(f"   Primeros 500 caracteres de la respuesta:")
        print(f"   {response.text[:500]}")
    else:
        print(f"   ⚠️ Status inesperado: {response.status_code}")

except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Verificar proceso Gunicorn
print("3. Verificando proceso del servidor...")
import subprocess
try:
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    gunicorn_processes = [line for line in result.stdout.split('\n') if 'gunicorn' in line.lower()]

    if gunicorn_processes:
        print(f"   ✅ Encontrados {len(gunicorn_processes)} procesos gunicorn:")
        for proc in gunicorn_processes[:3]:  # Mostrar solo los primeros 3
            print(f"   {proc.strip()}")
    else:
        print("   ⚠️ No se encontraron procesos gunicorn")

except Exception as e:
    print(f"   ⚠️ No se pudo verificar procesos: {e}")

print()
print("="*70)
print()

# Comando para reiniciar manualmente
print("💡 Si el servidor no responde correctamente:")
print("   1. Reinicia el servicio desde Render Dashboard")
print("   2. O ejecuta: pkill -HUP gunicorn")
print()
