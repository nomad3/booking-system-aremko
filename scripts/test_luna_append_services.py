#!/usr/bin/env python
"""
Script para probar agregar servicios a reserva existente
Ejecutar: python scripts/test_luna_append_services.py
"""

import urllib.request
import urllib.error
import json
import sys
import uuid

print("\n" + "="*60)
print("PRUEBA DE LUNA API - AGREGAR SERVICIOS A RESERVA")
print("="*60)

base_url = "https://aremko.cl/ventas"
api_key = "wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms"

resultados = []

# PASO 1: Crear una reserva inicial
print("\n" + "-"*60)
print("PASO 1: Crear Reserva Inicial (Solo Tina)")
print("-"*60)

idempotency_key = f"test-append-{uuid.uuid4().hex[:16]}"
reserva_id = None

try:
    url = f"{base_url}/api/luna/reservas/create/"

    body = json.dumps({
        "idempotency_key": idempotency_key,
        "cliente": {
            "nombre": "María López Test Append",
            "email": "maria.append@example.com",
            "telefono": "+56976543210",
            "documento_identidad": "22222222-2",
            "region_id": 14,
            "comuna_id": 31
        },
        "servicios": [
            {
                "servicio_id": 12,  # Tina Calbuco
                "fecha": "2026-05-10",
                "hora": "14:00",
                "cantidad_personas": 4
            }
        ],
        "metodo_pago": "pendiente",
        "notas": "Reserva inicial para test de append"
    }).encode('utf-8')

    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('X-Luna-API-Key', api_key)
    req.add_header('Content-Type', 'application/json')

    response = urllib.request.urlopen(req, timeout=10)
    data = json.loads(response.read().decode())

    if response.status == 201 and data.get('success'):
        reserva_id = data['reserva']['id']
        total_inicial = data['reserva']['total']
        print(f"✅ Reserva creada exitosamente")
        print(f"   ID: {reserva_id}")
        print(f"   Total inicial: ${total_inicial:,.0f}")
        print(f"   Servicios: 1 (Tina)")
        resultados.append(("Crear Reserva Inicial", True, f"ID: {reserva_id}"))
    else:
        print(f"❌ Error creando reserva inicial")
        resultados.append(("Crear Reserva Inicial", False, "Error"))
        sys.exit(1)

except urllib.error.HTTPError as e:
    if e.code == 307:
        new_url = e.headers.get('Location')
        try:
            req = urllib.request.Request(new_url, data=body, method='POST')
            req.add_header('X-Luna-API-Key', api_key)
            req.add_header('Content-Type', 'application/json')
            response = urllib.request.urlopen(req, timeout=10)
            data = json.loads(response.read().decode())
            if data.get('success'):
                reserva_id = data['reserva']['id']
                print(f"✅ Reserva creada: {reserva_id}")
                resultados.append(("Crear Reserva Inicial", True, f"ID: {reserva_id}"))
            else:
                resultados.append(("Crear Reserva Inicial", False, "Error"))
                sys.exit(1)
        except Exception as e2:
            print(f"❌ Error: {e2}")
            resultados.append(("Crear Reserva Inicial", False, str(e2)))
            sys.exit(1)
    else:
        print(f"❌ HTTP Error {e.code}")
        resultados.append(("Crear Reserva Inicial", False, f"HTTP {e.code}"))
        sys.exit(1)

except Exception as e:
    print(f"❌ Error: {e}")
    resultados.append(("Crear Reserva Inicial", False, str(e)))
    sys.exit(1)

# PASO 2: Agregar otra tina a la reserva (mismo tipo de servicio)
print("\n" + "-"*60)
print(f"PASO 2: Agregar Otra Tina a Reserva {reserva_id}")
print("-"*60)

try:
    url = f"{base_url}/api/luna/reservas/{reserva_id}/servicios/"
    print(f"URL: {url}")

    body = json.dumps({
        "servicios": [
            {
                "servicio_id": 13,  # Tina Hornopirén (si existe) o 14 (Tina Puelo)
                "fecha": "2026-05-10",
                "hora": "18:00",
                "cantidad_personas": 4
            }
        ]
    }).encode('utf-8')

    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('X-Luna-API-Key', api_key)
    req.add_header('Content-Type', 'application/json')

    response = urllib.request.urlopen(req, timeout=10)
    data = json.loads(response.read().decode())

    print(f"✅ Status Code: {response.status}")
    print(f"   Respuesta: {json.dumps(data, indent=2, ensure_ascii=False)}")

    if data.get('success'):
        servicios_agregados = len(data.get('servicios_agregados', []))
        nuevo_total = data.get('nuevo_total', 0)
        descuentos = data.get('total_descuentos', 0)

        print(f"\n   📊 RESULTADO:")
        print(f"   ✅ Servicios agregados: {servicios_agregados}")
        print(f"   💰 Nuevo total: ${nuevo_total:,.0f}")
        if descuentos > 0:
            print(f"   🎉 Descuentos aplicados: ${descuentos:,.0f}")

        resultados.append(("Agregar Otra Tina", True, f"Total: ${nuevo_total:,.0f}"))
    else:
        resultados.append(("Agregar Masajes", False, "Error"))

except urllib.error.HTTPError as e:
    if e.code == 307:
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
                resultados.append(("Agregar Otra Tina", True, "OK"))
            else:
                resultados.append(("Agregar Otra Tina", False, "Error"))
        except urllib.error.HTTPError as e2:
            print(f"❌ Error después de redirect: HTTP {e2.code}")
            try:
                error_data = json.loads(e2.read().decode())
                print(f"   Detalles: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                pass
            resultados.append(("Agregar Otra Tina", False, f"HTTP {e2.code}"))
    else:
        print(f"❌ HTTP Error {e.code}")
        try:
            error_data = json.loads(e.read().decode())
            print(f"   Detalles: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
        except:
            pass
        resultados.append(("Agregar Masajes", False, f"HTTP {e.code}"))

except Exception as e:
    print(f"❌ Error: {e}")
    resultados.append(("Agregar Masajes", False, str(e)))

# PASO 3: Intentar agregar a reserva inexistente (debe fallar)
print("\n" + "-"*60)
print("PASO 3: Agregar a Reserva Inexistente (debe fallar 404)")
print("-"*60)

try:
    url = f"{base_url}/api/luna/reservas/99999/servicios/"

    body = json.dumps({
        "servicios": [
            {
                "servicio_id": 12,
                "fecha": "2026-05-10",
                "hora": "18:00",
                "cantidad_personas": 2
            }
        ]
    }).encode('utf-8')

    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('X-Luna-API-Key', api_key)
    req.add_header('Content-Type', 'application/json')

    response = urllib.request.urlopen(req, timeout=10)
    print(f"⚠️  Debería haber rechazado con 404")
    resultados.append(("Reserva Inexistente", False, "No rechazó"))

except urllib.error.HTTPError as e:
    if e.code == 404:
        print(f"✅ Correctamente rechazado con status 404")
        try:
            error_data = json.loads(e.read().decode())
            print(f"   Mensaje: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
        except:
            pass
        resultados.append(("Reserva Inexistente", True, "404 correcto"))
    elif e.code == 307:
        new_url = e.headers.get('Location')
        try:
            req = urllib.request.Request(new_url, data=body, method='POST')
            req.add_header('X-Luna-API-Key', api_key)
            req.add_header('Content-Type', 'application/json')
            urllib.request.urlopen(req, timeout=10)
            resultados.append(("Reserva Inexistente", False, "No rechazó"))
        except urllib.error.HTTPError as e2:
            if e2.code == 404:
                print(f"✅ Correctamente rechazado con 404")
                resultados.append(("Reserva Inexistente", True, "404 correcto"))
            else:
                resultados.append(("Reserva Inexistente", False, f"HTTP {e2.code}"))
    else:
        resultados.append(("Reserva Inexistente", False, f"HTTP {e.code}"))

except Exception as e:
    print(f"❌ Error: {e}")
    resultados.append(("Reserva Inexistente", False, str(e)))

# Resumen
print("\n" + "="*60)
print("RESUMEN DE PRUEBAS - AGREGAR SERVICIOS")
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
    print("🎉 TESTS COMPLETADOS EXITOSAMENTE")
    print("\nEl endpoint de agregar servicios está funcionando correctamente.")
    print(f"\nReserva de prueba creada: RES-{reserva_id}")
    sys.exit(0)
else:
    print("⚠️  ALGUNOS TESTS FALLARON")
    print("\nRevisa los errores arriba y corrige antes de continuar.")
    sys.exit(1)
