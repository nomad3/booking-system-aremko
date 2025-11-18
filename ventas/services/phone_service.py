# -*- coding: utf-8 -*-
"""
Servicio centralizado para normalización y validación de teléfonos
Garantiza formato consistente +56XXXXXXXXX en todo el sistema
"""

import re
import logging
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class PhoneService:
    """
    Servicio centralizado para manejo de teléfonos en formato estándar +56XXXXXXXXX
    """

    @staticmethod
    def normalize_phone(phone_str):
        """
        Normaliza número de teléfono a formato estándar +56XXXXXXXXX

        Formatos de entrada soportados:
        - +56958655810 → +56958655810
        - 56958655810 → +56958655810
        - 958655810 → +56958655810
        - 9 5865 5810 → +56958655810
        - +56 9 5865 5810 → +56958655810
        - (56) 9-5865-5810 → +56958655810

        Args:
            phone_str: String con número de teléfono en cualquier formato

        Returns:
            str: Teléfono normalizado en formato +56XXXXXXXXX o None si inválido
        """
        if not phone_str or str(phone_str).strip() == '':
            return None

        # Convertir a string y limpiar
        phone = str(phone_str).strip()

        # PRIMERO: Validar que no contenga letras antes de hacer cualquier limpieza
        if re.search(r'[a-zA-Z]', phone):
            logger.warning(f"Teléfono contiene letras (inválido): {phone_str}")
            return None

        # Remover caracteres no numéricos (excepto +)
        phone_clean = re.sub(r'[^0-9+]', '', phone)

        # Remover todos los + para limpiar, luego agregarlo al inicio
        phone_digits = phone_clean.replace('+', '')

        # Validar que solo contenga dígitos
        if not phone_digits.isdigit():
            logger.warning(f"Teléfono contiene caracteres no válidos: {phone_str}")
            return None

        # Validar longitud mínima
        if len(phone_digits) < 8:
            logger.warning(f"Teléfono muy corto: {phone_str}")
            return None

        # CASO 1: Ya tiene código país 56 (Chile)
        if phone_digits.startswith('56'):
            # Debe ser 56 + 9 dígitos (móvil) = 11 total
            if len(phone_digits) == 11 and phone_digits[2] == '9':
                result = f'+{phone_digits}'
                logger.info(f"Teléfono normalizado (con 56): {phone_str} → {result}")
                return result
            else:
                logger.warning(f"Teléfono chileno con formato incorrecto: {phone_str} (debe ser 56 + 9XXXXXXXX)")
                return None

        # CASO 2: Móvil chileno sin código país (9XXXXXXXX)
        elif phone_digits.startswith('9') and len(phone_digits) == 9:
            result = f'+56{phone_digits}'
            logger.info(f"Teléfono normalizado (móvil): {phone_str} → {result}")
            return result

        # CASO 3: Número de 11 dígitos que empieza con 56 pero sin + inicial
        elif len(phone_digits) == 11 and phone_digits.startswith('56') and phone_digits[2] == '9':
            result = f'+{phone_digits}'
            logger.info(f"Teléfono normalizado (11 dígitos): {phone_str} → {result}")
            return result

        # CASO 4: Otros formatos no soportados
        else:
            logger.warning(f"Formato de teléfono no soportado: {phone_str} (dígitos: {phone_digits})")
            return None

    @staticmethod
    def generate_search_variants(phone_str):
        """
        Genera múltiples variantes de búsqueda para encontrar teléfonos con
        diferentes formatos en la base de datos

        Args:
            phone_str: Teléfono ingresado por usuario

        Returns:
            list: Lista de variantes para buscar en BD
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

        logger.info(f"Variantes generadas para '{phone_str}': {unique_variants}")
        return unique_variants

    @staticmethod
    def validate_phone_format(phone_str):
        """
        Valida si un teléfono cumple con el formato estándar +56XXXXXXXXX

        Args:
            phone_str: Teléfono a validar

        Returns:
            tuple: (is_valid: bool, error_message: str)
        """
        if not phone_str:
            return False, "Teléfono requerido"

        # Intentar normalizar
        normalized = PhoneService.normalize_phone(phone_str)

        if not normalized:
            return False, "Formato de teléfono inválido. Use formato +56958655810"

        # Validar formato final
        if not re.match(r'^\+56[9][0-9]{8}$', normalized):
            return False, "Debe ser un número móvil chileno: +56 9 XXXXXXXX"

        return True, ""

    @staticmethod
    def format_phone_for_display(phone_str):
        """
        Formatea teléfono para mostrar de forma amigable al usuario

        Args:
            phone_str: Teléfono en formato +56XXXXXXXXX

        Returns:
            str: Teléfono formateado para display (ej: +56 9 5865 5810)
        """
        if not phone_str:
            return ""

        # Normalizar primero
        normalized = PhoneService.normalize_phone(phone_str)
        if not normalized:
            return phone_str  # Devolver original si no se puede normalizar

        # Formatear: +56 9 XXXX XXXX
        if len(normalized) == 12 and normalized.startswith('+569'):
            return f"{normalized[:4]} {normalized[4]} {normalized[5:9]} {normalized[9:]}"

        return normalized


# Función de conveniencia para mantener compatibilidad
def normalize_phone(phone_str):
    """Wrapper para mantener compatibilidad con código existente"""
    return PhoneService.normalize_phone(phone_str)