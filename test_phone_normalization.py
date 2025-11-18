#!/usr/bin/env python3
"""
Script de prueba para validar la normalización robusta de teléfonos
Prueba diferentes formatos y casos edge para asegurar que la solución funciona correctamente
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.services.phone_service import PhoneService
from ventas.services.cliente_service import ClienteService
from ventas.models import Cliente

def test_phone_normalization():
    """Prueba la normalización de teléfonos con diferentes formatos"""

    print("=" * 80)
    print("🧪 PRUEBAS DE NORMALIZACIÓN DE TELÉFONOS")
    print("=" * 80)

    # Casos de prueba: (input, expected_output)
    test_cases = [
        # Casos válidos
        ("+56958655810", "+56958655810"),
        ("56958655810", "+56958655810"),
        ("958655810", "+56958655810"),
        ("9 5865 5810", "+56958655810"),
        ("+56 9 5865 5810", "+56958655810"),
        ("(56) 9-5865-5810", "+56958655810"),
        ("+56 9 8765 4321", "+56987654321"),
        ("9-8765-4321", "+56987654321"),
        ("  +56 9 1234 5678  ", "+56912345678"),  # Con espacios

        # Casos inválidos
        ("1234567", None),  # Muy corto
        ("abcd958655810", None),  # Con letras
        ("55958655810", None),  # Código país incorrecto
        ("", None),  # Vacío
        ("56858655810", None),  # No móvil (no empieza con 9)
        ("+569586558101", None),  # Muy largo
    ]

    passed = 0
    failed = 0

    for input_phone, expected in test_cases:
        result = PhoneService.normalize_phone(input_phone)

        if result == expected:
            print(f"✅ '{input_phone}' → '{result}' (esperado: '{expected}')")
            passed += 1
        else:
            print(f"❌ '{input_phone}' → '{result}' (esperado: '{expected}')")
            failed += 1

    print(f"\n📊 Resultados: {passed} pasaron, {failed} fallaron")
    return failed == 0

def test_search_variants():
    """Prueba la generación de variantes de búsqueda"""

    print("\n" + "=" * 80)
    print("🔍 PRUEBAS DE VARIANTES DE BÚSQUEDA")
    print("=" * 80)

    test_cases = [
        "+56958655810",
        "958655810",
        "9 5865 5810",
        "+56 9 5865 5810"
    ]

    for phone in test_cases:
        variants = PhoneService.generate_search_variants(phone)
        print(f"\n📱 Input: '{phone}'")
        print(f"   Variantes generadas: {variants}")

        # Verificar que se incluyen las variantes principales
        expected_normalized = PhoneService.normalize_phone(phone)
        if expected_normalized:
            if expected_normalized not in variants:
                print(f"   ⚠️ Falta variante normalizada: {expected_normalized}")

def test_client_search_integration():
    """Prueba la integración completa de búsqueda de clientes"""

    print("\n" + "=" * 80)
    print("👤 PRUEBAS DE INTEGRACIÓN DE BÚSQUEDA DE CLIENTES")
    print("=" * 80)

    # Crear un cliente de prueba si no existe
    test_phone = "+56987654321"
    test_name = "Cliente Test Phone Normalization"

    try:
        # Intentar crear cliente de prueba
        cliente_test, created = Cliente.objects.get_or_create(
            telefono=test_phone,
            defaults={
                'nombre': test_name,
                'email': 'test@aremko.cl'
            }
        )

        if created:
            print(f"✅ Cliente de prueba creado: {cliente_test.nombre} ({cliente_test.telefono})")
        else:
            print(f"ℹ️ Cliente de prueba existente: {cliente_test.nombre} ({cliente_test.telefono})")

        # Probar diferentes formatos de búsqueda para el mismo cliente
        search_formats = [
            "+56987654321",     # Formato completo
            "56987654321",      # Sin +
            "987654321",        # Solo móvil
            "9 8765 4321",      # Con espacios
            "+56 9 8765 4321",  # Formato display
        ]

        all_found = True

        for search_format in search_formats:
            cliente_encontrado, telefono_norm = ClienteService.buscar_cliente_por_telefono(search_format)

            if cliente_encontrado and cliente_encontrado.id == cliente_test.id:
                print(f"✅ Búsqueda '{search_format}' → Encontrado: {cliente_encontrado.nombre}")
            else:
                print(f"❌ Búsqueda '{search_format}' → No encontrado (debería encontrar {test_name})")
                all_found = False

        # Probar datos completos
        print(f"\n🔍 Probando obtención de datos completos...")
        datos_completos = ClienteService.obtener_datos_completos_cliente(cliente_test)

        if datos_completos['encontrado']:
            cliente_data = datos_completos['cliente']
            print(f"✅ Datos completos obtenidos:")
            print(f"   - Nombre: {cliente_data['nombre']}")
            print(f"   - Email: {cliente_data['email']}")
            print(f"   - Teléfono: {cliente_data['telefono']}")
            print(f"   - Display: {cliente_data['telefono_display']}")
            print(f"   - Visitas: {cliente_data['numero_visitas']}")
            print(f"   - Datos completos: {cliente_data['datos_completos']}")
        else:
            print(f"❌ Error obteniendo datos completos")
            all_found = False

        return all_found

    except Exception as e:
        print(f"❌ Error en pruebas de integración: {e}")
        return False

def test_create_or_update_client():
    """Prueba la creación y actualización de clientes"""

    print("\n" + "=" * 80)
    print("💾 PRUEBAS DE CREACIÓN/ACTUALIZACIÓN DE CLIENTES")
    print("=" * 80)

    # Datos de prueba
    test_data = {
        'telefono': '9 1111 2222',  # Formato no normalizado
        'nombre': 'Cliente Prueba Actualización',
        'email': 'update.test@aremko.cl'
    }

    try:
        # Primera llamada - debería crear
        cliente1, created1, errors1 = ClienteService.crear_o_actualizar_cliente(test_data)

        if errors1:
            print(f"❌ Errores en primera creación: {errors1}")
            return False

        if created1:
            print(f"✅ Cliente creado correctamente: {cliente1.nombre} ({cliente1.telefono})")
        else:
            print(f"ℹ️ Cliente ya existía: {cliente1.nombre} ({cliente1.telefono})")

        # Segunda llamada con datos actualizados - debería actualizar
        test_data_update = test_data.copy()
        test_data_update['nombre'] = 'Cliente Prueba ACTUALIZADO'
        test_data_update['email'] = 'updated@aremko.cl'

        cliente2, created2, errors2 = ClienteService.crear_o_actualizar_cliente(test_data_update)

        if errors2:
            print(f"❌ Errores en actualización: {errors2}")
            return False

        if not created2 and cliente2.nombre == test_data_update['nombre']:
            print(f"✅ Cliente actualizado correctamente: {cliente2.nombre} ({cliente2.email})")
        else:
            print(f"❌ Error en actualización: created={created2}, nombre={cliente2.nombre}")
            return False

        # Verificar que es el mismo cliente
        if cliente1.id == cliente2.id:
            print(f"✅ Mismo cliente actualizado (ID: {cliente1.id})")
        else:
            print(f"❌ Se creó cliente duplicado (IDs: {cliente1.id} vs {cliente2.id})")
            return False

        return True

    except Exception as e:
        print(f"❌ Error en pruebas de creación/actualización: {e}")
        return False

def main():
    """Ejecuta todas las pruebas"""

    print("🚀 Iniciando pruebas del sistema de normalización de teléfonos...")

    results = []

    # Ejecutar todas las pruebas
    results.append(("Normalización", test_phone_normalization()))
    test_search_variants()  # Solo informativa
    results.append(("Búsqueda de clientes", test_client_search_integration()))
    results.append(("Creación/Actualización", test_create_or_update_client()))

    # Resumen final
    print("\n" + "=" * 80)
    print("📋 RESUMEN DE PRUEBAS")
    print("=" * 80)

    passed = 0
    total = 0

    for name, result in results:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"{name}: {status}")
        if result:
            passed += 1
        total += 1

    success_rate = (passed / total) * 100 if total > 0 else 0

    print(f"\nResultado final: {passed}/{total} pruebas pasaron ({success_rate:.1f}%)")

    if passed == total:
        print("\n🎉 ¡Todas las pruebas pasaron! La solución está lista para producción.")
    else:
        print(f"\n⚠️ {total - passed} pruebas fallaron. Revisar implementación.")

if __name__ == "__main__":
    main()