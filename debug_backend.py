#!/usr/bin/env python3
"""
Script para debuggear el problema del backend con el cliente
"""

# Simular exactamente lo que hace el backend
class MockPhoneService:
    @staticmethod
    def normalize_phone(phone_str):
        if not phone_str or str(phone_str).strip() == '':
            return None

        import re
        phone = str(phone_str).strip()

        # Validar que no contenga letras
        if re.search(r'[a-zA-Z]', phone):
            print(f"⚠️ Teléfono contiene letras (inválido): {phone_str}")
            return None

        # Remover caracteres no numéricos (excepto +)
        phone_clean = re.sub(r'[^0-9+]', '', phone)
        phone_digits = phone_clean.replace('+', '')

        if not phone_digits.isdigit():
            print(f"⚠️ Teléfono contiene caracteres no válidos: {phone_str}")
            return None

        if len(phone_digits) < 8:
            print(f"⚠️ Teléfono muy corto: {phone_str}")
            return None

        # CASO 1: Ya tiene código país 56
        if phone_digits.startswith('56'):
            if len(phone_digits) == 11 and phone_digits[2] == '9':
                result = f'+{phone_digits}'
                print(f"✅ Teléfono normalizado (con 56): {phone_str} → {result}")
                return result
            else:
                print(f"⚠️ Teléfono chileno con formato incorrecto: {phone_str}")
                return None

        # CASO 2: Móvil sin código país
        elif phone_digits.startswith('9') and len(phone_digits) == 9:
            result = f'+56{phone_digits}'
            print(f"✅ Teléfono normalizado (móvil): {phone_str} → {result}")
            return result

        # CASO 3: 11 dígitos empezando con 56
        elif len(phone_digits) == 11 and phone_digits.startswith('56') and phone_digits[2] == '9':
            result = f'+{phone_digits}'
            print(f"✅ Teléfono normalizado (11 dígitos): {phone_str} → {result}")
            return result

        else:
            print(f"⚠️ Formato no soportado: {phone_str} (dígitos: {phone_digits})")
            return None

    @staticmethod
    def generate_search_variants(phone_str):
        import re
        variants = []

        if not phone_str:
            return variants

        # Formato normalizado principal
        normalized = MockPhoneService.normalize_phone(phone_str)
        if normalized:
            variants.append(normalized)

        # Limpiar entrada
        phone_clean = re.sub(r'[^0-9+]', '', str(phone_str))
        phone_digits = phone_clean.replace('+', '')

        if phone_digits:
            if phone_digits.startswith('56') and len(phone_digits) == 11:
                variants.extend([f'+{phone_digits}', phone_digits])
                mobile_only = phone_digits[2:]
                if len(mobile_only) == 9:
                    variants.append(mobile_only)

            elif phone_digits.startswith('9') and len(phone_digits) == 9:
                variants.extend([
                    phone_digits,
                    f'+56{phone_digits}',
                    f'56{phone_digits}'
                ])

        # Remover duplicados
        seen = set()
        unique_variants = []
        for variant in variants:
            if variant not in seen:
                seen.add(variant)
                unique_variants.append(variant)

        print(f"🔍 Variantes generadas para '{phone_str}': {unique_variants}")
        return unique_variants

def test_backend_logic():
    print("🧪 TESTING BACKEND LOGIC")
    print("=" * 50)

    # Probar exactamente lo que recibe el backend
    telefono_raw = '+56994436882'
    print(f"\n📱 Input del frontend: {telefono_raw}")

    # Simular lo que hace ClienteService.buscar_cliente_por_telefono
    print("\n🔍 Generando variantes de búsqueda:")
    variants = MockPhoneService.generate_search_variants(telefono_raw)

    print("\n📋 Variantes que se buscarían en la base de datos:")
    for i, variant in enumerate(variants, 1):
        print(f"   {i}. '{variant}'")

    print("\n❓ POSIBLES PROBLEMAS:")
    print("1. Cliente guardado en BD con formato diferente a estas variantes")
    print("2. Error en query de búsqueda en base de datos")
    print("3. Cliente no existe realmente en la base de datos")

    # Probar formatos alternativos que podrían estar en la BD
    possible_formats = [
        '+56994436882',   # Normalizado
        '56994436882',    # Sin +
        '994436882',      # Solo móvil
        '9 9443 6882',    # Con espacios
        '+56 9 9443 6882', # Con espacios y +
        '+56 994436882',   # Espacio después del código
    ]

    print(f"\n🔍 TESTING formatos posibles en la BD:")
    for fmt in possible_formats:
        normalized = MockPhoneService.normalize_phone(fmt)
        variants_test = MockPhoneService.generate_search_variants(fmt)
        print(f"   BD: '{fmt}' → Normalizado: '{normalized}' → Variantes: {len(variants_test)}")

        # Verificar si habría match
        if '+56994436882' in variants_test:
            print(f"   ✅ MATCH: Este formato encontraría al cliente")
        else:
            print(f"   ❌ NO MATCH: Este formato NO encontraría al cliente")

if __name__ == "__main__":
    test_backend_logic()