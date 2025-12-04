#!/usr/bin/env python
"""
Script para probar la lógica de packs localmente
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko.settings')
django.setup()

from ventas.models import PackDescuento
from ventas.services.pack_descuento_service import PackDescuentoService

def test_pack_logic():
    """Probar la lógica del pack de descuento"""

    print("="*60)
    print("PRUEBA DE LÓGICA DE PACK DESCUENTOS")
    print("="*60)

    # Buscar pack de $35,000
    pack_35k = PackDescuento.objects.filter(valor_descuento=35000).first()
    if not pack_35k:
        print("⚠️ No se encontró pack con descuento de $35,000")
        return

    print(f"\n📦 Pack encontrado: {pack_35k.nombre}")
    print(f"   Descuento: ${pack_35k.valor_descuento:,}")

    # Simulación de carrito con 1 persona
    print("\n🧪 TEST 1: Tina + Masaje con 1 persona")
    cart_1_persona = {
        'servicios': [
            {
                'id': 1,
                'nombre': 'Tina Hidromasaje Villarrica',
                'precio': 30000,
                'fecha': '2024-12-10',
                'hora': '14:00',
                'cantidad_personas': 1,
                'tipo_servicio': 'tina',
                'subtotal': 30000
            },
            {
                'id': 2,
                'nombre': 'Masaje Relajación',
                'precio': 40000,
                'fecha': '2024-12-10',
                'hora': '16:00',
                'cantidad_personas': 1,
                'tipo_servicio': 'masaje',
                'subtotal': 40000
            }
        ],
        'giftcards': [],
        'total': 70000
    }

    packs_aplicados = PackDescuentoService.detectar_packs_aplicables(cart_1_persona['servicios'])

    if packs_aplicados:
        print("   ❌ ERROR: Se aplicó descuento con 1 persona (no debería)")
        for pack_info in packs_aplicados:
            print(f"      - {pack_info['pack'].nombre}: ${pack_info['descuento']:,}")
    else:
        print("   ✅ CORRECTO: No se aplicó descuento con 1 persona")

    # Simulación de carrito con 2 personas
    print("\n🧪 TEST 2: Tina + Masaje con 2 personas")
    cart_2_personas = {
        'servicios': [
            {
                'id': 1,
                'nombre': 'Tina Hidromasaje Villarrica',
                'precio': 30000,
                'fecha': '2024-12-10',
                'hora': '14:00',
                'cantidad_personas': 2,
                'tipo_servicio': 'tina',
                'subtotal': 60000
            },
            {
                'id': 2,
                'nombre': 'Masaje Relajación',
                'precio': 40000,
                'fecha': '2024-12-10',
                'hora': '16:00',
                'cantidad_personas': 2,
                'tipo_servicio': 'masaje',
                'subtotal': 80000
            }
        ],
        'giftcards': [],
        'total': 140000
    }

    packs_aplicados = PackDescuentoService.detectar_packs_aplicables(cart_2_personas['servicios'])

    if packs_aplicados:
        print("   ✅ CORRECTO: Se aplicó descuento con 2 personas")
        for pack_info in packs_aplicados:
            print(f"      - {pack_info['pack'].nombre}: ${pack_info['descuento']:,}")
    else:
        print("   ❌ ERROR: No se aplicó descuento con 2 personas (debería aplicar)")

    # Simulación mixta
    print("\n🧪 TEST 3: Tina con 1 persona + Masaje con 2 personas")
    cart_mixto = {
        'servicios': [
            {
                'id': 1,
                'nombre': 'Tina Hidromasaje Villarrica',
                'precio': 30000,
                'fecha': '2024-12-10',
                'hora': '14:00',
                'cantidad_personas': 1,
                'tipo_servicio': 'tina',
                'subtotal': 30000
            },
            {
                'id': 2,
                'nombre': 'Masaje Relajación',
                'precio': 40000,
                'fecha': '2024-12-10',
                'hora': '16:00',
                'cantidad_personas': 2,
                'tipo_servicio': 'masaje',
                'subtotal': 80000
            }
        ],
        'giftcards': [],
        'total': 110000
    }

    packs_aplicados = PackDescuentoService.detectar_packs_aplicables(cart_mixto['servicios'])

    if packs_aplicados:
        print("   ❌ ERROR: Se aplicó descuento con cantidades mixtas (no debería)")
        for pack_info in packs_aplicados:
            print(f"      - {pack_info['pack'].nombre}: ${pack_info['descuento']:,}")
    else:
        print("   ✅ CORRECTO: No se aplicó descuento con cantidades mixtas")

    print("\n" + "="*60)
    print("PRUEBAS COMPLETADAS")
    print("="*60)

if __name__ == '__main__':
    test_pack_logic()