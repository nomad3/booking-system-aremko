"""
Tests de normalización de teléfono — soporte internacional (2026-07-22).

Contexto: PhoneService.normalize_phone solo aceptaba formato chileno; cualquier
número extranjero (ej. brasileño +55...) devolvía None → Cliente.save() lanzaba
ValidationError → 500 al crear un cliente extranjero desde el admin. Se agregó
el CASO 5 (internacional): un número con + y código de país != 56 se respeta.

No toca la BD (solo prueba la función pura), así que es inmune al drift AR-034.

Ejecutar:
    python manage.py test ventas.tests_phone_internacional
"""
from __future__ import annotations

from django.test import SimpleTestCase

from ventas.services.phone_service import PhoneService


class NormalizePhoneInternacionalTest(SimpleTestCase):

    def test_chilenos_siguen_funcionando(self):
        """Regresión: los formatos chilenos no cambian."""
        casos = {
            '+56958655810': '+56958655810',
            '56958655810': '+56958655810',
            '958655810': '+56958655810',
            '9 5865 5810': '+56958655810',
            '+56 9 5865 5810': '+56958655810',
            '(56) 9-5865-5810': '+56958655810',
        }
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(PhoneService.normalize_phone(entrada), esperado)

    def test_internacionales_con_prefijo_se_aceptan(self):
        """Turistas extranjeros: con + y código de país, se respetan tal cual."""
        casos = {
            '+5511987654321': '+5511987654321',        # Brasil móvil
            '+55 11 98765-4321': '+5511987654321',      # Brasil con formato
            '+54 9 11 1234-5678': '+5491112345678',     # Argentina
            '+1 234 567 8901': '+12345678901',          # USA
        }
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(PhoneService.normalize_phone(entrada), esperado)

    def test_normalizacion_es_idempotente(self):
        """Normalizar dos veces da lo mismo (el form normaliza y el save() otra vez)."""
        for entrada in ('+56958655810', '958655810', '+5511987654321', '+54 9 11 1234-5678'):
            with self.subTest(entrada=entrada):
                una_vez = PhoneService.normalize_phone(entrada)
                self.assertEqual(PhoneService.normalize_phone(una_vez), una_vez)

    def test_invalidos_siguen_rechazados(self):
        """Casos que deben seguir devolviendo None."""
        casos = [
            '1234567',            # muy corto
            'abc958655810',       # con letras
            '5511987654321',      # internacional SIN + → ambiguo, se rechaza
            '+56212345678',       # chileno con + pero no es móvil válido
            '',                   # vacío
            None,                 # None
        ]
        for entrada in casos:
            with self.subTest(entrada=entrada):
                self.assertIsNone(PhoneService.normalize_phone(entrada))


class ValidarTelefonoLunaTest(SimpleTestCase):
    """
    El wrapper de Luna (validar_telefono_chileno) delega en PhoneService, así que
    también acepta internacionales. Antes rechazaba a un turista extranjero.
    """

    def test_chileno_valido(self):
        from ventas.views.luna_api_views import validar_telefono_chileno
        es_valido, mensaje, norm = validar_telefono_chileno('912345678')
        self.assertTrue(es_valido)
        self.assertEqual(norm, '+56912345678')
        self.assertEqual(mensaje, '')

    def test_brasileno_valido(self):
        from ventas.views.luna_api_views import validar_telefono_chileno
        es_valido, mensaje, norm = validar_telefono_chileno('+55 11 98765-4321')
        self.assertTrue(es_valido)
        self.assertEqual(norm, '+5511987654321')

    def test_invalido_devuelve_mensaje(self):
        from ventas.views.luna_api_views import validar_telefono_chileno
        es_valido, mensaje, norm = validar_telefono_chileno('123')
        self.assertFalse(es_valido)
        self.assertEqual(norm, '')
        self.assertTrue(mensaje)  # hay un mensaje de error para el usuario
