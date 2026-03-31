#!/usr/bin/env python
"""
Script para probar Luna API Fase 1
Ejecutar: python scripts/test_luna_api_phase1.py
"""

import urllib.request
import json
import sys

print("\n" + "="*60)
print("PRUEBA DE LUNA API - FASE 1")
print("="*60)

base_url = "https://aremko.cl"
api_key = "wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms"

resultados = []

# Test 1: Health Check (sin autenticación)
print("\n" + "-"*60)
print("TEST 1: Health Check (público)")
print("-"*60)

try:
    url = f"{base_url}/api/luna/health"
    print(f"URL: {url}")

    response = urllib.request.urlopen(url, timeout=10)
    data = json.loads(response.read().decode())

    print(f"✅ Status Code: {response.status}")
    print(f"   Respuesta: {json.dumps(data, indent=2)}")
    resultados.append(("Health Check", True, "OK"))

except Exception as e:
    print(f"❌ Error: {e}")
    resultados.append(("Health Check", False, str(e)))

# Test 2: Test Connection (con autenticación)
print("\n" + "-"*60)
print("TEST 2: Test Connection (con API Key)")
print("-"*60)

try:
    url = f"{base_url}/api/luna/test"
    print(f"URL: {url}")
    print(f"Header: X-Luna-API-Key: {api_key[:20]}...")

    req = urllib.request.Request(url)
    req.add_header('X-Luna-API-Key', api_key)

    response = urllib.request.urlopen(req, timeout=10)
    data = json.loads(response.read().decode())

    print(f"✅ Status Code: {response.status}")
    print(f"   Respuesta: {json.dumps(data, indent=2)}")

    if data.get('success'):
        resultados.append(("Test Connection", True, "Autenticación OK"))
    else:
        resultados.append(("Test Connection", False, "Success=false"))

except urllib.error.HTTPError as e:
    print(f"❌ HTTP Error {e.code}: {e.reason}")
    try:
        error_data = json.loads(e.read().decode())
        print(f"   Detalles: {json.dumps(error_data, indent=2)}")
    except:
        pass
    resultados.append(("Test Connection", False, f"HTTP {e.code}"))

except Exception as e:
    print(f"❌ Error: {e}")
    resultados.append(("Test Connection", False, str(e)))

# Test 3: Test con API Key Incorrecta (debe fallar)
print("\n" + "-"*60)
print("TEST 3: Test con API Key Incorrecta (debe fallar)")
print("-"*60)

try:
    url = f"{base_url}/api/luna/test"
    print(f"URL: {url}")
    print(f"Header: X-Luna-API-Key: CLAVE_INCORRECTA")

    req = urllib.request.Request(url)
    req.add_header('X-Luna-API-Key', 'CLAVE_INCORRECTA_123')

    response = urllib.request.urlopen(req, timeout=10)
    print(f"⚠️  Debería haber rechazado pero aceptó (Status: {response.status})")
    resultados.append(("API Key Incorrecta", False, "No rechazó clave inválida"))

except urllib.error.HTTPError as e:
    if e.code in [401, 403]:
        print(f"✅ Correctamente rechazada con status {e.code}")
        try:
            error_data = json.loads(e.read().decode())
            print(f"   Mensaje: {json.dumps(error_data, indent=2)}")
        except:
            pass
        resultados.append(("API Key Incorrecta", True, f"Rechazada correctamente ({e.code})"))
    else:
        print(f"⚠️  Error inesperado: {e.code}")
        resultados.append(("API Key Incorrecta", False, f"Error {e.code}"))

except Exception as e:
    print(f"❌ Error inesperado: {e}")
    resultados.append(("API Key Incorrecta", False, str(e)))

# Test 4: Listar Regiones
print("\n" + "-"*60)
print("TEST 4: Listar Regiones y Comunas")
print("-"*60)

try:
    url = f"{base_url}/api/luna/regiones"
    print(f"URL: {url}")

    req = urllib.request.Request(url)
    req.add_header('X-Luna-API-Key', api_key)

    response = urllib.request.urlopen(req, timeout=10)
    data = json.loads(response.read().decode())

    print(f"✅ Status Code: {response.status}")

    if data.get('success'):
        regiones = data.get('regiones', [])
        print(f"   Regiones encontradas: {len(regiones)}")

        if regiones:
            # Mostrar primera región
            primera = regiones[0]
            print(f"\n   Ejemplo - {primera['nombre']}:")
            print(f"   ID: {primera['id']}")
            print(f"   Comunas: {len(primera.get('comunas', []))}")

            if primera.get('comunas'):
                print(f"   Primeras comunas:")
                for comuna in primera['comunas'][:3]:
                    print(f"      - {comuna['nombre']} (ID: {comuna['id']})")

            resultados.append(("Listar Regiones", True, f"{len(regiones)} regiones"))
        else:
            print(f"   ⚠️  No se encontraron regiones")
            resultados.append(("Listar Regiones", False, "Sin regiones"))
    else:
        print(f"   ❌ Success=false")
        resultados.append(("Listar Regiones", False, "Success=false"))

except Exception as e:
    print(f"❌ Error: {e}")
    resultados.append(("Listar Regiones", False, str(e)))

# Test 5: Validar Disponibilidad (placeholder)
print("\n" + "-"*60)
print("TEST 5: Validar Disponibilidad (placeholder - Fase 2)")
print("-"*60)

try:
    url = f"{base_url}/api/luna/reservas/validar"
    print(f"URL: {url}")

    body = json.dumps({
        "servicios": [
            {
                "servicio_id": 12,
                "fecha": "2026-04-01",
                "hora": "14:30",
                "cantidad_personas": 2
            }
        ]
    }).encode('utf-8')

    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('X-Luna-API-Key', api_key)
    req.add_header('Content-Type', 'application/json')

    response = urllib.request.urlopen(req, timeout=10)
    data = json.loads(response.read().decode())

    print(f"✅ Status Code: {response.status}")
    print(f"   Respuesta: {json.dumps(data, indent=2)}")

    if 'Fase 2' in data.get('mensaje', ''):
        resultados.append(("Validar Disponibilidad", True, "Placeholder OK"))
    else:
        resultados.append(("Validar Disponibilidad", True, "Funciona"))

except Exception as e:
    print(f"❌ Error: {e}")
    resultados.append(("Validar Disponibilidad", False, str(e)))

# Test 6: Crear Reserva (placeholder)
print("\n" + "-"*60)
print("TEST 6: Crear Reserva (placeholder - Fase 3)")
print("-"*60)

try:
    url = f"{base_url}/api/luna/reservas/create"
    print(f"URL: {url}")

    body = json.dumps({
        "idempotency_key": "test-phase1-001",
        "cliente": {
            "nombre": "Test Cliente",
            "email": "test@test.com",
            "telefono": "+56912345678",
            "documento_identidad": "12345678-9",
            "region_id": 1,
            "comuna_id": 10
        },
        "servicios": [
            {
                "servicio_id": 12,
                "fecha": "2026-04-01",
                "hora": "14:30",
                "cantidad_personas": 2
            }
        ]
    }).encode('utf-8')

    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('X-Luna-API-Key', api_key)
    req.add_header('Content-Type', 'application/json')

    response = urllib.request.urlopen(req, timeout=10)
    data = json.loads(response.read().decode())

    print(f"✅ Status Code: {response.status}")
    print(f"   Respuesta: {json.dumps(data, indent=2)}")

    if 'Fase 3' in data.get('mensaje', ''):
        resultados.append(("Crear Reserva", True, "Placeholder OK"))
    else:
        resultados.append(("Crear Reserva", True, "Funciona"))

except Exception as e:
    print(f"❌ Error: {e}")
    resultados.append(("Crear Reserva", False, str(e)))

# Resumen
print("\n" + "="*60)
print("RESUMEN DE PRUEBAS")
print("="*60)

total = len(resultados)
exitosos = sum(1 for _, success, _ in resultados if success)
fallidos = total - exitosos

print(f"\nTotal de tests: {total}")
print(f"✅ Exitosos: {exitosos}")
print(f"❌ Fallidos: {fallidos}")

print("\nDetalle:")
for test_name, success, mensaje in resultados:
    status = "✅" if success else "❌"
    print(f"  {status} {test_name:30s} - {mensaje}")

print("\n" + "="*60)

if fallidos == 0:
    print("🎉 FASE 1 COMPLETADA EXITOSAMENTE")
    print("\nLa infraestructura de Luna API está funcionando correctamente.")
    print("Lista para continuar con Fase 2 (Validaciones).")
    sys.exit(0)
else:
    print("⚠️  ALGUNOS TESTS FALLARON")
    print("\nRevisa los errores arriba y corrige antes de continuar.")
    sys.exit(1)
