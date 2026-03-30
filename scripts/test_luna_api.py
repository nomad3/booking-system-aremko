#!/usr/bin/env python
"""
Script para probar la API que usa Luna
Verifica que la disponibilidad se muestre correctamente
"""

import os
import sys
import django
import requests
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.conf import settings
from ventas.models import Servicio, CategoriaServicio
from django.db.models import Q

def test_luna_api():
    print("\n" + "="*60)
    print("PRUEBA DE API PARA LUNA AI")
    print("="*60)

    # Configuración base
    base_url = "https://aremko.cl"
    api_key = getattr(settings, 'LUNA_API_KEY', 'wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms')

    print(f"\n📍 Base URL: {base_url}")
    print(f"🔑 API Key: {api_key[:20]}...")

    # Fecha de mañana
    tomorrow = datetime.now().date() + timedelta(days=1)
    tomorrow_str = tomorrow.strftime('%Y-%m-%d')
    day_name = tomorrow.strftime('%A').lower()

    print(f"\n📅 Fecha de prueba: {tomorrow} ({day_name})")

    # Headers para la API
    headers = {
        'X-API-Key': api_key,
        'Accept': 'application/json'
    }

    print("\n" + "-"*50)
    print("PRUEBA 1: API Summary")
    print("-"*50)

    try:
        url = f"{base_url}/api/v1/availability/summary/?date={tomorrow_str}"
        print(f"🔗 URL: {url}")

        response = requests.get(url, headers=headers, timeout=10)
        print(f"📊 Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("✅ Respuesta exitosa:")
            print(f"   Tinajas disponibles: {data.get('tubs', {}).get('available_count', 0)}")
            print(f"   Masajes disponibles: {data.get('massages', {}).get('available_count', 0)}")
            print(f"   Cabañas disponibles: {data.get('cabins', {}).get('available_count', 0)}")
        else:
            print(f"❌ Error: {response.text}")
    except Exception as e:
        print(f"❌ Error en request: {e}")

    print("\n" + "-"*50)
    print("PRUEBA 2: Tinajas (Hot Tubs)")
    print("-"*50)

    try:
        url = f"{base_url}/api/v1/availability/tinajas/?date={tomorrow_str}"
        print(f"🔗 URL: {url}")

        response = requests.get(url, headers=headers, timeout=10)
        print(f"📊 Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            tubs = data.get('tubs', [])
            print(f"✅ Tinajas encontradas: {len(tubs)}")

            # Buscar específicamente Calbuco
            calbuco_found = False
            for tub in tubs:
                if 'calbuco' in tub.get('name', '').lower():
                    calbuco_found = True
                    slots = tub.get('available_slots', [])
                    print(f"\n🎯 TINA CALBUCO:")
                    print(f"   ID: {tub.get('id')}")
                    print(f"   Nombre: {tub.get('name')}")
                    print(f"   Slots disponibles: {len(slots)}")
                    if slots:
                        print(f"   Horarios: {', '.join(slots[:10])}")
                    else:
                        print("   ⚠️  NO HAY SLOTS DISPONIBLES")

            if not calbuco_found:
                print("\n⚠️  Tina Calbuco no aparece en la respuesta")

            # Mostrar otras tinajas
            print("\nOtras tinajas:")
            for tub in tubs[:3]:  # Primeras 3
                if 'calbuco' not in tub.get('name', '').lower():
                    print(f"  - {tub.get('name')}: {len(tub.get('available_slots', []))} slots")
        else:
            print(f"❌ Error: {response.text}")
    except Exception as e:
        print(f"❌ Error en request: {e}")

    print("\n" + "-"*50)
    print("PRUEBA 3: API Antigua (ventas/get-available-hours)")
    print("-"*50)

    # Buscar ID de Tina Calbuco
    calbuco = Servicio.objects.filter(
        Q(nombre__icontains='calbuco') | Q(id=4)
    ).first()

    if calbuco:
        try:
            # Esta es la API que realmente está funcionando
            url = f"{base_url}/ventas/get-available-hours/?servicio_id={calbuco.id}&fecha={tomorrow_str}"
            print(f"🔗 URL: {url}")

            response = requests.get(url, timeout=10)  # Sin auth header
            print(f"📊 Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    horas = data.get('horas_disponibles', [])
                    print(f"✅ Horas disponibles: {len(horas)}")
                    if horas:
                        print(f"   Horarios: {', '.join(horas[:10])}")
                    else:
                        print("   ⚠️  NO HAY HORAS DISPONIBLES")
                        print("\n   🔍 Esto indica que slots_disponibles no tiene")
                        print(f"      configuración para '{day_name}'")
                else:
                    print(f"❌ Respuesta sin éxito: {data}")
            else:
                print(f"❌ Error: {response.text}")
        except Exception as e:
            print(f"❌ Error en request: {e}")
    else:
        print("❌ No se encontró Tina Calbuco en la base de datos")

    print("\n" + "-"*50)
    print("PRUEBA 4: Verificación Local de Slots")
    print("-"*50)

    if calbuco:
        print(f"\n🔍 Verificando slots de {calbuco.nombre} (ID: {calbuco.id})")
        print(f"   Tipo de slots_disponibles: {type(calbuco.slots_disponibles)}")

        if isinstance(calbuco.slots_disponibles, dict):
            print(f"   Días configurados: {list(calbuco.slots_disponibles.keys())}")

            if day_name in calbuco.slots_disponibles:
                slots = calbuco.slots_disponibles[day_name]
                print(f"   ✅ Slots para '{day_name}': {len(slots) if slots else 0}")
                if slots:
                    print(f"      Horarios: {slots[:5]}...")
            else:
                print(f"   ❌ NO hay configuración para '{day_name}'")
                print("\n   💡 ESTE ES EL PROBLEMA:")
                print("      Los slots están configurados con días en español")
                print("      pero el código busca días en inglés")
                print("\n   ✅ SOLUCIÓN:")
                print("      Ejecuta: python scripts/fix_slots_language.py")

    print("\n" + "="*60)
    print("FIN DE PRUEBAS")
    print("="*60)

if __name__ == "__main__":
    test_luna_api()