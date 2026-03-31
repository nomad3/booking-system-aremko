#!/usr/bin/env python
"""
Script para probar las APIs de disponibilidad sin curl
Ejecutar: python scripts/test_api_curl.py
"""

import urllib.request
import json

print("\n" + "="*60)
print("PRUEBA DE APIs DE DISPONIBILIDAD")
print("="*60)

fecha = "2026-04-01"  # Miércoles
servicio_id = 12  # Tina Calbuco

# Test 1: API antigua (ventas)
print("\n" + "-"*60)
print("1. API ANTIGUA (ventas/get-available-hours)")
print("-"*60)

url1 = f'https://aremko.cl/ventas/get-available-hours/?servicio_id={servicio_id}&fecha={fecha}'
print(f"URL: {url1}")

try:
    response = urllib.request.urlopen(url1)
    data = json.loads(response.read().decode())

    print(f"\n✅ Respuesta exitosa:")
    print(f"   Success: {data.get('success')}")

    if data.get('success'):
        horas = data.get('horas_disponibles', [])
        print(f"   Horas disponibles: {len(horas)}")
        if horas:
            print(f"   Horarios: {horas}")
        else:
            print(f"   ⚠️  Sin horarios disponibles")
    else:
        print(f"   Error: {data.get('error')}")

except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: API nueva (con autenticación)
print("\n" + "-"*60)
print("2. API NUEVA (api/v1/availability/tinajas)")
print("-"*60)

url2 = f'https://aremko.cl/api/v1/availability/tinajas/?date={fecha}'
api_key = 'wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms'

print(f"URL: {url2}")

try:
    req = urllib.request.Request(url2)
    req.add_header('X-API-Key', api_key)

    response = urllib.request.urlopen(req)
    data = json.loads(response.read().decode())

    print(f"\n✅ Respuesta exitosa:")

    if 'tubs' in data:
        tubs = data['tubs']
        print(f"   Tinajas encontradas: {len(tubs)}")

        # Buscar Tina Calbuco
        for tub in tubs:
            if 'calbuco' in tub.get('name', '').lower():
                print(f"\n   🎯 TINA CALBUCO:")
                print(f"      ID: {tub.get('id')}")
                print(f"      Nombre: {tub.get('name')}")
                print(f"      Slots: {len(tub.get('available_slots', []))}")
                slots = tub.get('available_slots', [])
                if slots:
                    print(f"      Horarios: {slots}")
                else:
                    print(f"      ⚠️  Sin slots disponibles")
                break
        else:
            print(f"   ⚠️  Tina Calbuco no encontrada en la respuesta")
    else:
        print(f"   Respuesta: {data}")

except urllib.error.HTTPError as e:
    print(f"❌ HTTP Error {e.code}: {e.reason}")
    try:
        error_data = json.loads(e.read().decode())
        print(f"   Detalles: {error_data}")
    except:
        pass
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: API summary
print("\n" + "-"*60)
print("3. API NUEVA - SUMMARY")
print("-"*60)

url3 = f'https://aremko.cl/api/v1/availability/summary/?date={fecha}'

print(f"URL: {url3}")

try:
    req = urllib.request.Request(url3)
    req.add_header('X-API-Key', api_key)

    response = urllib.request.urlopen(req)
    data = json.loads(response.read().decode())

    print(f"\n✅ Respuesta exitosa:")
    print(f"   Tinajas disponibles: {data.get('tubs', {}).get('available_count', 0)}")
    print(f"   Masajes disponibles: {data.get('massages', {}).get('available_count', 0)}")
    print(f"   Cabañas disponibles: {data.get('cabins', {}).get('available_count', 0)}")

except urllib.error.HTTPError as e:
    print(f"❌ HTTP Error {e.code}: {e.reason}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*60)
print("FIN DE PRUEBAS")
print("="*60)