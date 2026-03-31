#!/usr/bin/env python
"""
Script para probar Luna API Fase 3 - Creación de Reservas
Ejecutar: python scripts/test_luna_api_phase3.py
"""

import urllib.request
import urllib.error
import json
import sys
import uuid

print("\n" + "="*60)
print("PRUEBA DE LUNA API - FASE 3 (CREACIÓN DE RESERVAS)")
print("="*60)

base_url = "https://aremko.cl/ventas"
api_key = "wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms"

resultados = []

# Test 1: Crear reserva completa - Caso exitoso
print("\n" + "-"*60)
print("TEST 1: Crear Reserva Completa - Caso Exitoso")
print("-"*60)

try:
    url = f"{base_url}/api/luna/reservas/create/"
    print(f"URL: {url}")

    # Generar idempotency key único
    idempotency_key = f"test-phase3-{uuid.uuid4().hex[:16]}"
    print(f"Idempotency Key: {idempotency_key}")

    body = json.dumps({
        "idempotency_key": idempotency_key,
        "cliente": {
            "nombre": "Juan Pérez Test Luna",
            "email": "juan.test.luna@example.com",
            "telefono": "+56987654321",
            "documento_identidad": "11111111-1",  # RUT válido de prueba
            "region_id": 14,  # Región Los Lagos
            "comuna_id": 31   # Calbuco (pertenece a Región 14)
        },
        "servicios": [
            {
                "servicio_id": 12,
                "fecha": "2026-04-20",
                "hora": "15:00",
                "cantidad_personas": 4
            }
        ],
        "metodo_pago": "pendiente",
        "notas": "Reserva de prueba desde Luna API - Fase 3"
    }).encode('utf-8')

    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('X-Luna-API-Key', api_key)
    req.add_header('Content-Type', 'application/json')

    response = urllib.request.urlopen(req, timeout=10)
    data = json.loads(response.read().decode())

    print(f"✅ Status Code: {response.status}")
    print(f"   Respuesta: {json.dumps(data, indent=2, ensure_ascii=False)}")

    if data.get('success') and data.get('reserva'):
        reserva_id = data['reserva']['id']
        total = data['reserva']['total']
        resultados.append(("Crear Reserva Completa", True, f"ID: {reserva_id}, Total: ${total:,.0f}"))
    else:
        resultados.append(("Crear Reserva Completa", False, "Sin datos de reserva"))

except urllib.error.HTTPError as e:
    if e.code == 307:
        # Seguir redirect
        new_url = e.headers.get('Location')
        print(f"   Siguiendo redirect a: {new_url}")
        try:
            req = urllib.request.Request(new_url, data=body, method='POST')
            req.add_header('X-Luna-API-Key', api_key)
            req.add_header('Content-Type', 'application/json')
            response = urllib.request.urlopen(req, timeout=10)
            data = json.loads(response.read().decode())
            print(f"✅ Status Code: {response.status}")
            print(f"   Respuesta: {json.dumps(data, indent=2, ensure_ascii=False)}")
            if data.get('success'):
                reserva_id = data['reserva']['id']
                resultados.append(("Crear Reserva Completa", True, f"ID: {reserva_id}"))
            else:
                resultados.append(("Crear Reserva Completa", False, "Error"))
        except urllib.error.HTTPError as e2:
            print(f"❌ Error después de redirect: HTTP {e2.code}")
            try:
                error_data = json.loads(e2.read().decode())
                print(f"   Detalles: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                pass
            resultados.append(("Crear Reserva Completa", False, f"HTTP {e2.code}"))
    else:
        print(f"❌ HTTP Error {e.code}")
        try:
            error_data = json.loads(e.read().decode())
            print(f"   Detalles: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
        except:
            pass
        resultados.append(("Crear Reserva Completa", False, f"HTTP {e.code}"))

except Exception as e:
    print(f"❌ Error: {e}")
    resultados.append(("Crear Reserva Completa", False, str(e)))

# Test 2: Idempotencia - Mismo idempotency_key
print("\n" + "-"*60)
print("TEST 2: Idempotencia - Duplicar con mismo idempotency_key")
print("-"*60)

try:
    url = f"{base_url}/api/luna/reservas/create/"
    print(f"URL: {url}")
    print(f"Usando mismo Idempotency Key: {idempotency_key}")

    # Usar el mismo body que el test anterior
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('X-Luna-API-Key', api_key)
    req.add_header('Content-Type', 'application/json')

    response = urllib.request.urlopen(req, timeout=10)
    data = json.loads(response.read().decode())

    print(f"✅ Status Code: {response.status}")
    print(f"   Respuesta: {json.dumps(data, indent=2, ensure_ascii=False)}")

    if data.get('success') and data.get('duplicada'):
        print("   ✅ Correctamente detectada como duplicada")
        resultados.append(("Idempotencia", True, "Duplicada detectada"))
    else:
        print("   ⚠️  No detectó como duplicada")
        resultados.append(("Idempotencia", False, "No detectó duplicada"))

except urllib.error.HTTPError as e:
    if e.code == 307:
        new_url = e.headers.get('Location')
        try:
            req = urllib.request.Request(new_url, data=body, method='POST')
            req.add_header('X-Luna-API-Key', api_key)
            req.add_header('Content-Type', 'application/json')
            response = urllib.request.urlopen(req, timeout=10)
            data = json.loads(response.read().decode())
            if data.get('duplicada'):
                resultados.append(("Idempotencia", True, "Duplicada detectada"))
            else:
                resultados.append(("Idempotencia", False, "No detectó duplicada"))
        except Exception as e2:
            resultados.append(("Idempotencia", False, str(e2)))
    else:
        resultados.append(("Idempotencia", False, f"HTTP {e.code}"))

except Exception as e:
    print(f"❌ Error: {e}")
    resultados.append(("Idempotencia", False, str(e)))

# Test 3: Validación - Cliente sin nombre (debe fallar)
print("\n" + "-"*60)
print("TEST 3: Validación - Cliente sin nombre (debe fallar)")
print("-"*60)

try:
    url = f"{base_url}/api/luna/reservas/create/"

    body = json.dumps({
        "idempotency_key": f"test-fail-{uuid.uuid4().hex[:8]}",
        "cliente": {
            "nombre": "",  # Nombre vacío - debe fallar
            "email": "test@example.com",
            "telefono": "+56987654321",
            "region_id": 14,
            "comuna_id": 31
        },
        "servicios": [
            {
                "servicio_id": 12,
                "fecha": "2026-04-20",
                "hora": "15:00",
                "cantidad_personas": 4
            }
        ]
    }).encode('utf-8')

    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('X-Luna-API-Key', api_key)
    req.add_header('Content-Type', 'application/json')

    response = urllib.request.urlopen(req, timeout=10)
    print(f"⚠️  Debería haber rechazado cliente sin nombre")
    resultados.append(("Validación Cliente", False, "No rechazó"))

except urllib.error.HTTPError as e:
    if e.code == 400:
        print(f"✅ Correctamente rechazado con status {e.code}")
        try:
            error_data = json.loads(e.read().decode())
            print(f"   Mensaje: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
        except:
            pass
        resultados.append(("Validación Cliente", True, "Rechazado correctamente"))
    elif e.code == 307:
        new_url = e.headers.get('Location')
        try:
            req = urllib.request.Request(new_url, data=body, method='POST')
            req.add_header('X-Luna-API-Key', api_key)
            req.add_header('Content-Type', 'application/json')
            urllib.request.urlopen(req, timeout=10)
            print(f"⚠️  Debería haber rechazado")
            resultados.append(("Validación Cliente", False, "No rechazó"))
        except urllib.error.HTTPError as e2:
            if e2.code == 400:
                print(f"✅ Correctamente rechazado")
                resultados.append(("Validación Cliente", True, "Rechazado"))
            else:
                resultados.append(("Validación Cliente", False, f"HTTP {e2.code}"))
    else:
        resultados.append(("Validación Cliente", False, f"HTTP {e.code}"))

except Exception as e:
    print(f"❌ Error: {e}")
    resultados.append(("Validación Cliente", False, str(e)))

# Test 4: Validación - Sin idempotency_key (debe fallar)
print("\n" + "-"*60)
print("TEST 4: Validación - Sin idempotency_key (debe fallar)")
print("-"*60)

try:
    url = f"{base_url}/api/luna/reservas/create/"

    body = json.dumps({
        # Sin idempotency_key
        "cliente": {
            "nombre": "Juan Pérez",
            "email": "test@example.com",
            "telefono": "+56987654321",
            "region_id": 14,
            "comuna_id": 31
        },
        "servicios": [
            {
                "servicio_id": 12,
                "fecha": "2026-04-20",
                "hora": "15:00",
                "cantidad_personas": 4
            }
        ]
    }).encode('utf-8')

    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('X-Luna-API-Key', api_key)
    req.add_header('Content-Type', 'application/json')

    response = urllib.request.urlopen(req, timeout=10)
    print(f"⚠️  Debería haber rechazado sin idempotency_key")
    resultados.append(("Sin Idempotency Key", False, "No rechazó"))

except urllib.error.HTTPError as e:
    if e.code == 400:
        print(f"✅ Correctamente rechazado")
        resultados.append(("Sin Idempotency Key", True, "Rechazado"))
    elif e.code == 307:
        new_url = e.headers.get('Location')
        try:
            req = urllib.request.Request(new_url, data=body, method='POST')
            req.add_header('X-Luna-API-Key', api_key)
            req.add_header('Content-Type', 'application/json')
            urllib.request.urlopen(req, timeout=10)
            resultados.append(("Sin Idempotency Key", False, "No rechazó"))
        except urllib.error.HTTPError as e2:
            if e2.code == 400:
                resultados.append(("Sin Idempotency Key", True, "Rechazado"))
            else:
                resultados.append(("Sin Idempotency Key", False, f"HTTP {e2.code}"))
    else:
        resultados.append(("Sin Idempotency Key", False, f"HTTP {e.code}"))

except Exception as e:
    resultados.append(("Sin Idempotency Key", False, str(e)))

# Resumen
print("\n" + "="*60)
print("RESUMEN DE PRUEBAS - FASE 3")
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
    print("🎉 FASE 3 COMPLETADA EXITOSAMENTE")
    print("\nLa API de creación de reservas está funcionando correctamente.")
    print("Luna puede ahora crear reservas completas desde WhatsApp.")
    sys.exit(0)
else:
    print("⚠️  ALGUNOS TESTS FALLARON")
    print("\nRevisa los errores arriba y corrige antes de continuar.")
    sys.exit(1)
