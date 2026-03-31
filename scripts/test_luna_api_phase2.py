#!/usr/bin/env python
"""
Script para probar Luna API Fase 2 - Validaciones
Ejecutar: python scripts/test_luna_api_phase2.py
"""

import urllib.request
import urllib.error
import json
import sys

print("\n" + "="*60)
print("PRUEBA DE LUNA API - FASE 2 (VALIDACIONES)")
print("="*60)

base_url = "https://aremko.cl/ventas"
api_key = "wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms"

resultados = []

# Test 1: Validar disponibilidad - Caso exitoso
print("\n" + "-"*60)
print("TEST 1: Validar Disponibilidad - Caso Exitoso")
print("-"*60)

try:
    url = f"{base_url}/api/luna/reservas/validar/"
    print(f"URL: {url}")

    # Usar un servicio que sabemos existe (ID 12 típicamente es una tina)
    body = json.dumps({
        "servicios": [
            {
                "servicio_id": 12,
                "fecha": "2026-04-15",
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
    print(f"   Respuesta: {json.dumps(data, indent=2, ensure_ascii=False)}")

    if data.get('success') and len(data.get('disponibilidad', [])) > 0:
        resultados.append(("Validar - Caso Exitoso", True, "OK"))
    else:
        resultados.append(("Validar - Caso Exitoso", False, "Sin disponibilidad"))

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
                resultados.append(("Validar - Caso Exitoso", True, "OK"))
            else:
                resultados.append(("Validar - Caso Exitoso", False, "Error"))
        except urllib.error.HTTPError as e2:
            print(f"❌ Error después de redirect: HTTP {e2.code}")
            try:
                error_data = json.loads(e2.read().decode())
                print(f"   Detalles del error: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                pass
            resultados.append(("Validar - Caso Exitoso", False, f"HTTP {e2.code}"))
        except Exception as e2:
            print(f"❌ Error después de redirect: {e2}")
            resultados.append(("Validar - Caso Exitoso", False, str(e2)))
    else:
        print(f"❌ HTTP Error {e.code}: {e.reason}")
        try:
            error_data = json.loads(e.read().decode())
            print(f"   Detalles: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
        except:
            pass
        resultados.append(("Validar - Caso Exitoso", False, f"HTTP {e.code}"))

except Exception as e:
    print(f"❌ Error: {e}")
    resultados.append(("Validar - Caso Exitoso", False, str(e)))

# Test 2: Validar con servicio inexistente
print("\n" + "-"*60)
print("TEST 2: Validar con Servicio Inexistente (debe fallar)")
print("-"*60)

try:
    url = f"{base_url}/api/luna/reservas/validar/"
    print(f"URL: {url}")

    body = json.dumps({
        "servicios": [
            {
                "servicio_id": 99999,
                "fecha": "2026-04-15",
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
    print(f"⚠️  Debería haber rechazado pero aceptó")
    resultados.append(("Servicio Inexistente", False, "No detectó error"))

except urllib.error.HTTPError as e:
    if e.code == 400:
        print(f"✅ Correctamente rechazado con status {e.code}")
        try:
            error_data = json.loads(e.read().decode())
            print(f"   Mensaje: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            if 'errores' in error_data:
                resultados.append(("Servicio Inexistente", True, "Error detectado correctamente"))
            else:
                resultados.append(("Servicio Inexistente", False, "Respuesta incorrecta"))
        except:
            resultados.append(("Servicio Inexistente", True, "Error detectado"))
    elif e.code == 307:
        # Seguir redirect
        new_url = e.headers.get('Location')
        print(f"   Siguiendo redirect a: {new_url}")
        try:
            req = urllib.request.Request(new_url, data=body, method='POST')
            req.add_header('X-Luna-API-Key', api_key)
            req.add_header('Content-Type', 'application/json')
            response = urllib.request.urlopen(req, timeout=10)
            data = json.loads(response.read().decode())
            print(f"⚠️  Debería haber rechazado pero aceptó")
            resultados.append(("Servicio Inexistente", False, "No detectó error"))
        except urllib.error.HTTPError as e2:
            if e2.code == 400:
                print(f"✅ Correctamente rechazado con status {e2.code}")
                resultados.append(("Servicio Inexistente", True, "Error detectado"))
            else:
                resultados.append(("Servicio Inexistente", False, f"HTTP {e2.code}"))
    else:
        print(f"⚠️  Error inesperado: {e.code}")
        resultados.append(("Servicio Inexistente", False, f"HTTP {e.code}"))

except Exception as e:
    print(f"❌ Error inesperado: {e}")
    resultados.append(("Servicio Inexistente", False, str(e)))

# Test 3: Validar con fecha pasada (debe fallar)
print("\n" + "-"*60)
print("TEST 3: Validar con Fecha Pasada (debe fallar)")
print("-"*60)

try:
    url = f"{base_url}/api/luna/reservas/validar/"
    print(f"URL: {url}")

    body = json.dumps({
        "servicios": [
            {
                "servicio_id": 12,
                "fecha": "2020-01-01",
                "hora": "14:30",
                "cantidad_personas": 2
            }
        ]
    }).encode('utf-8')

    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('X-Luna-API-Key', api_key)
    req.add_header('Content-Type', 'application/json')

    response = urllib.request.urlopen(req, timeout=10)
    print(f"⚠️  Debería haber rechazado fecha pasada")
    resultados.append(("Fecha Pasada", False, "No detectó error"))

except urllib.error.HTTPError as e:
    if e.code == 400:
        print(f"✅ Correctamente rechazado con status {e.code}")
        try:
            error_data = json.loads(e.read().decode())
            print(f"   Mensaje: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
        except:
            pass
        resultados.append(("Fecha Pasada", True, "Error detectado correctamente"))
    elif e.code == 307:
        # Seguir redirect y verificar error
        new_url = e.headers.get('Location')
        try:
            req = urllib.request.Request(new_url, data=body, method='POST')
            req.add_header('X-Luna-API-Key', api_key)
            req.add_header('Content-Type', 'application/json')
            urllib.request.urlopen(req, timeout=10)
            print(f"⚠️  Debería haber rechazado fecha pasada")
            resultados.append(("Fecha Pasada", False, "No detectó error"))
        except urllib.error.HTTPError as e2:
            if e2.code == 400:
                print(f"✅ Correctamente rechazado")
                resultados.append(("Fecha Pasada", True, "Error detectado"))
            else:
                resultados.append(("Fecha Pasada", False, f"HTTP {e2.code}"))
    else:
        resultados.append(("Fecha Pasada", False, f"HTTP {e.code}"))

except Exception as e:
    print(f"❌ Error: {e}")
    resultados.append(("Fecha Pasada", False, str(e)))

# Test 4: Validar múltiples servicios con descuento
print("\n" + "-"*60)
print("TEST 4: Múltiples Servicios - Detectar Descuentos")
print("-"*60)

try:
    url = f"{base_url}/api/luna/reservas/validar/"
    print(f"URL: {url}")

    body = json.dumps({
        "servicios": [
            {
                "servicio_id": 12,
                "fecha": "2026-04-15",
                "hora": "14:30",
                "cantidad_personas": 2
            },
            {
                "servicio_id": 20,  # Intentar con un masaje si existe
                "fecha": "2026-04-15",
                "hora": "16:00",
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
    print(f"   Respuesta: {json.dumps(data, indent=2, ensure_ascii=False)}")

    if data.get('success'):
        num_descuentos = len(data.get('descuentos_aplicables', []))
        if num_descuentos > 0:
            resultados.append(("Múltiples Servicios", True, f"{num_descuentos} descuento(s) detectado(s)"))
        else:
            resultados.append(("Múltiples Servicios", True, "Sin descuentos"))
    else:
        resultados.append(("Múltiples Servicios", False, "Error en validación"))

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
                resultados.append(("Múltiples Servicios", True, "OK"))
            else:
                resultados.append(("Múltiples Servicios", False, "Error"))
        except urllib.error.HTTPError as e2:
            print(f"❌ Error después de redirect: HTTP {e2.code}")
            try:
                error_data = json.loads(e2.read().decode())
                print(f"   Detalles del error: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                pass
            resultados.append(("Múltiples Servicios", False, f"HTTP {e2.code}"))
        except Exception as e2:
            print(f"❌ Error: {e2}")
            resultados.append(("Múltiples Servicios", False, str(e2)))
    else:
        print(f"❌ HTTP Error {e.code}")
        resultados.append(("Múltiples Servicios", False, f"HTTP {e.code}"))

except Exception as e:
    print(f"❌ Error: {e}")
    resultados.append(("Múltiples Servicios", False, str(e)))

# Test 5: Validar capacidad excedida (debe fallar)
print("\n" + "-"*60)
print("TEST 5: Capacidad Excedida (debe fallar)")
print("-"*60)

try:
    url = f"{base_url}/api/luna/reservas/validar/"
    print(f"URL: {url}")

    body = json.dumps({
        "servicios": [
            {
                "servicio_id": 12,
                "fecha": "2026-04-15",
                "hora": "14:30",
                "cantidad_personas": 100  # Excede cualquier capacidad
            }
        ]
    }).encode('utf-8')

    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('X-Luna-API-Key', api_key)
    req.add_header('Content-Type', 'application/json')

    response = urllib.request.urlopen(req, timeout=10)
    print(f"⚠️  Debería haber rechazado capacidad excedida")
    resultados.append(("Capacidad Excedida", False, "No detectó error"))

except urllib.error.HTTPError as e:
    if e.code == 400:
        print(f"✅ Correctamente rechazado con status {e.code}")
        try:
            error_data = json.loads(e.read().decode())
            print(f"   Mensaje: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
        except:
            pass
        resultados.append(("Capacidad Excedida", True, "Error detectado"))
    elif e.code == 307:
        new_url = e.headers.get('Location')
        try:
            req = urllib.request.Request(new_url, data=body, method='POST')
            req.add_header('X-Luna-API-Key', api_key)
            req.add_header('Content-Type', 'application/json')
            urllib.request.urlopen(req, timeout=10)
            print(f"⚠️  Debería haber rechazado")
            resultados.append(("Capacidad Excedida", False, "No detectó error"))
        except urllib.error.HTTPError as e2:
            if e2.code == 400:
                print(f"✅ Correctamente rechazado")
                resultados.append(("Capacidad Excedida", True, "Error detectado"))
            else:
                resultados.append(("Capacidad Excedida", False, f"HTTP {e2.code}"))
    else:
        resultados.append(("Capacidad Excedida", False, f"HTTP {e.code}"))

except Exception as e:
    print(f"❌ Error: {e}")
    resultados.append(("Capacidad Excedida", False, str(e)))

# Resumen
print("\n" + "="*60)
print("RESUMEN DE PRUEBAS - FASE 2")
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
    print("🎉 FASE 2 COMPLETADA EXITOSAMENTE")
    print("\nLas validaciones de disponibilidad están funcionando correctamente.")
    print("Lista para continuar con Fase 3 (Creación de Reservas).")
    sys.exit(0)
else:
    print("⚠️  ALGUNOS TESTS FALLARON")
    print("\nRevisa los errores arriba y corrige antes de continuar.")
    sys.exit(1)
