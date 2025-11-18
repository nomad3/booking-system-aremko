#!/usr/bin/env python3
"""
Script de prueba simple para validar la normalización de teléfonos
Prueba solo las funciones de normalización sin necesidad de Django completo
"""

import re

class PhoneService:
    """
    Copia de la clase PhoneService para pruebas standalone
    """

    @staticmethod
    def normalize_phone(phone_str):
        """
        Normaliza número de teléfono a formato estándar +56XXXXXXXXX
        """
        if not phone_str or str(phone_str).strip() == '':
            return None

        # Convertir a string y limpiar
        phone = str(phone_str).strip()

        # PRIMERO: Validar que no contenga letras antes de hacer cualquier limpieza
        if re.search(r'[a-zA-Z]', phone):
            print(f"⚠️ Teléfono contiene letras (inválido): {phone_str}")
            return None

        # Remover caracteres no numéricos (excepto +)
        phone_clean = re.sub(r'[^0-9+]', '', phone)

        # Remover todos los + para limpiar, luego agregarlo al inicio
        phone_digits = phone_clean.replace('+', '')

        # Validar que solo contenga dígitos
        if not phone_digits.isdigit():
            print(f"⚠️ Teléfono contiene caracteres no válidos: {phone_str}")
            return None

        # Validar longitud mínima
        if len(phone_digits) < 8:
            print(f"⚠️ Teléfono muy corto: {phone_str}")
            return None

        # CASO 1: Ya tiene código país 56 (Chile)
        if phone_digits.startswith('56'):
            # Debe ser 56 + 9 dígitos (móvil) = 11 total
            if len(phone_digits) == 11 and phone_digits[2] == '9':
                result = f'+{phone_digits}'
                print(f"✅ Teléfono normalizado (con 56): {phone_str} → {result}")
                return result
            else:
                print(f"⚠️ Teléfono chileno con formato incorrecto: {phone_str} (debe ser 56 + 9XXXXXXXX)")
                return None

        # CASO 2: Móvil chileno sin código país (9XXXXXXXX)
        elif phone_digits.startswith('9') and len(phone_digits) == 9:
            result = f'+56{phone_digits}'
            print(f"✅ Teléfono normalizado (móvil): {phone_str} → {result}")
            return result

        # CASO 3: Número de 11 dígitos que empieza con 56 pero sin + inicial
        elif len(phone_digits) == 11 and phone_digits.startswith('56') and phone_digits[2] == '9':
            result = f'+{phone_digits}'
            print(f"✅ Teléfono normalizado (11 dígitos): {phone_str} → {result}")
            return result

        # CASO 4: Otros formatos no soportados
        else:
            print(f"⚠️ Formato de teléfono no soportado: {phone_str} (dígitos: {phone_digits})")
            return None

    @staticmethod
    def generate_search_variants(phone_str):
        """
        Genera múltiples variantes de búsqueda para encontrar teléfonos
        """
        variants = []

        if not phone_str:
            return variants

        # 1. Formato normalizado principal
        normalized = PhoneService.normalize_phone(phone_str)
        if normalized:
            variants.append(normalized)

        # 2. Limpiar entrada del usuario
        phone_clean = re.sub(r'[^0-9+]', '', str(phone_str))
        phone_digits = phone_clean.replace('+', '')

        if phone_digits:
            # 3. Variantes adicionales para búsqueda
            if phone_digits.startswith('56') and len(phone_digits) == 11:
                # +56958655810, 56958655810
                variants.extend([f'+{phone_digits}', phone_digits])
                # Solo móvil: 958655810
                mobile_only = phone_digits[2:]
                if len(mobile_only) == 9:
                    variants.append(mobile_only)

            elif phone_digits.startswith('9') and len(phone_digits) == 9:
                # 958655810, +56958655810, 56958655810
                variants.extend([
                    phone_digits,
                    f'+56{phone_digits}',
                    f'56{phone_digits}'
                ])

        # Remover duplicados manteniendo orden
        seen = set()
        unique_variants = []
        for variant in variants:
            if variant not in seen:
                seen.add(variant)
                unique_variants.append(variant)

        print(f"🔍 Variantes generadas para '{phone_str}': {unique_variants}")
        return unique_variants

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

    print("Ejecutando casos de prueba...")
    print("-" * 80)

    for input_phone, expected in test_cases:
        print(f"\n📱 Probando: '{input_phone}'")
        result = PhoneService.normalize_phone(input_phone)

        if result == expected:
            print(f"✅ PASÓ: '{input_phone}' → '{result}' (esperado: '{expected}')")
            passed += 1
        else:
            print(f"❌ FALLÓ: '{input_phone}' → '{result}' (esperado: '{expected}')")
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
        print(f"\n📱 Input: '{phone}'")
        variants = PhoneService.generate_search_variants(phone)

        # Verificar que se incluyen las variantes principales
        expected_normalized = PhoneService.normalize_phone(phone)
        if expected_normalized:
            if expected_normalized not in variants:
                print(f"   ⚠️ Falta variante normalizada: {expected_normalized}")
            else:
                print(f"   ✅ Variante normalizada incluida correctamente")

def test_problematic_cases():
    """Prueba casos específicos que podrían causar problemas"""

    print("\n" + "=" * 80)
    print("⚠️ PRUEBAS DE CASOS PROBLEMÁTICOS")
    print("=" * 80)

    # Casos que específicamente podrían fallar en el checkout del usuario
    problematic_cases = [
        "+56994436882",  # Caso específico del usuario
        "994436882",     # Sin código país
        "+56 9 9443 6882",  # Con espacios
        "9-9443-6882",   # Con guiones
    ]

    print("Probando casos específicos del error reportado...")
    print("-" * 80)

    for case in problematic_cases:
        print(f"\n🔍 Caso problemático: '{case}'")

        normalized = PhoneService.normalize_phone(case)
        if normalized:
            print(f"✅ Normalización exitosa: {normalized}")

            variants = PhoneService.generate_search_variants(case)
            print(f"   Variantes de búsqueda: {len(variants)} generadas")
        else:
            print(f"❌ Normalización falló")

def main():
    """Ejecuta todas las pruebas"""

    print("🚀 Iniciando pruebas del sistema de normalización de teléfonos...")

    results = []

    # Ejecutar todas las pruebas
    results.append(("Normalización básica", test_phone_normalization()))

    print("\n" + "="*40)
    test_search_variants()  # Solo informativa

    print("\n" + "="*40)
    test_problematic_cases()  # Solo informativa

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
        print("\n🎉 ¡Todas las pruebas de normalización pasaron!")
        print("💡 La lógica de normalización está lista para implementar.")

        print("\n📝 Próximos pasos recomendados:")
        print("   1. ✅ Implementar PhoneService en Django")
        print("   2. ✅ Actualizar ClienteService para usar búsqueda robusta")
        print("   3. ✅ Modificar vistas de checkout para usar nuevo servicio")
        print("   4. 🔄 Probar en entorno de desarrollo")
        print("   5. 📊 Validar con datos reales")
        print("   6. 🚀 Desplegar en producción")

    else:
        print(f"\n⚠️ {total - passed} pruebas fallaron. Revisar implementación.")

if __name__ == "__main__":
    main()