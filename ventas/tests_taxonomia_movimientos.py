"""
Tests para Operación Vuelta a Casa, Etapas 5.1 y 5.2.

Etapa 5.1 (este archivo): tests de detectar_cambios + taxonomia_a_dict.
Etapa 5.2: se ampliará con DetectarCelebracionesTests y
           GenerarMovimientosCelebracionesTests cuando llegue ese commit.

Ejecutar:
    python manage.py test ventas.tests_taxonomia_movimientos
"""

from __future__ import annotations

from unittest.mock import MagicMock

from django.test import TestCase

from ventas.services.taxonomia_movimientos_service import (
    Cambio,
    EJES,
    detectar_cambios,
    taxonomia_a_dict,
)


# ============================================================================
# Helpers para construir snapshots en los tests
# ============================================================================

def _snap(valor='', estilo='', contexto=''):
    """Crea un dict snapshot rápido para usar en tests."""
    return {
        'eje_valor': valor,
        'eje_estilo': estilo,
        'eje_contexto': contexto,
    }


# ============================================================================
# TaxonomiaADict — normalización
# ============================================================================

class TaxonomiaADictTests(TestCase):
    def test_none_devuelve_dict_de_strings_vacios(self):
        r = taxonomia_a_dict(None)
        self.assertEqual(r, {'eje_valor': '', 'eje_estilo': '', 'eje_contexto': ''})

    def test_dict_passes_through(self):
        d = _snap('En Riesgo', 'Amante de las Tinas', 'Visitante Pareja')
        self.assertEqual(taxonomia_a_dict(d), d)

    def test_dict_con_keys_faltantes_llena_con_vacios(self):
        r = taxonomia_a_dict({'eje_valor': 'Dormido'})
        self.assertEqual(r, {'eje_valor': 'Dormido', 'eje_estilo': '', 'eje_contexto': ''})

    def test_dict_con_valores_None_los_convierte_a_vacio(self):
        r = taxonomia_a_dict({'eje_valor': None, 'eje_estilo': 'X', 'eje_contexto': None})
        self.assertEqual(r, {'eje_valor': '', 'eje_estilo': 'X', 'eje_contexto': ''})

    def test_objeto_con_atributos(self):
        obj = MagicMock()
        obj.eje_valor = 'Leal'
        obj.eje_estilo = 'Amante de las Tinas'
        obj.eje_contexto = 'Visitante Pareja'
        r = taxonomia_a_dict(obj)
        self.assertEqual(r, {
            'eje_valor': 'Leal',
            'eje_estilo': 'Amante de las Tinas',
            'eje_contexto': 'Visitante Pareja',
        })

    def test_objeto_con_atributos_None(self):
        obj = MagicMock(spec=['eje_valor', 'eje_estilo', 'eje_contexto'])
        obj.eje_valor = None
        obj.eje_estilo = 'Devoto del Masaje'
        obj.eje_contexto = None
        r = taxonomia_a_dict(obj)
        self.assertEqual(r, {
            'eje_valor': '',
            'eje_estilo': 'Devoto del Masaje',
            'eje_contexto': '',
        })


# ============================================================================
# DetectarCambios — la función pura central
# ============================================================================

class DetectarCambiosTests(TestCase):
    def test_ambos_none_no_hay_cambios(self):
        self.assertEqual(detectar_cambios(None, None), [])

    def test_mismos_valores_no_hay_cambios(self):
        antes = _snap('Regular', 'Amante de las Tinas', 'Visitante Pareja')
        despues = _snap('Regular', 'Amante de las Tinas', 'Visitante Pareja')
        self.assertEqual(detectar_cambios(antes, despues), [])

    def test_solo_eje_valor_cambia(self):
        antes = _snap('Dormido', 'Amante de las Tinas', 'Visitante Pareja')
        despues = _snap('En Prueba', 'Amante de las Tinas', 'Visitante Pareja')
        cambios = detectar_cambios(antes, despues)
        self.assertEqual(len(cambios), 1)
        self.assertEqual(cambios[0], Cambio(
            eje='valor', valor_antes='Dormido', valor_despues='En Prueba',
        ))

    def test_solo_eje_estilo_cambia(self):
        antes = _snap('Regular', 'Probador Esporádico', 'Visitante Solo')
        despues = _snap('Regular', 'Devoto del Masaje', 'Visitante Solo')
        cambios = detectar_cambios(antes, despues)
        self.assertEqual(len(cambios), 1)
        self.assertEqual(cambios[0].eje, 'estilo')
        self.assertEqual(cambios[0].valor_despues, 'Devoto del Masaje')

    def test_solo_eje_contexto_cambia(self):
        antes = _snap('Regular', 'Amante de las Tinas', 'Visitante Solo')
        despues = _snap('Regular', 'Amante de las Tinas', 'Visitante Pareja')
        cambios = detectar_cambios(antes, despues)
        self.assertEqual(len(cambios), 1)
        self.assertEqual(cambios[0].eje, 'contexto')

    def test_los_tres_ejes_cambian(self):
        antes = _snap('Dormido', 'Probador Esporádico', 'Visitante Solo')
        despues = _snap('En Prueba', 'Devoto del Masaje', 'Visitante Pareja')
        cambios = detectar_cambios(antes, despues)
        self.assertEqual(len(cambios), 3)
        # Orden estable según constante EJES
        self.assertEqual([c.eje for c in cambios], list(EJES))

    def test_taxo_anterior_None_cliente_nuevo(self):
        # Cliente recién clasificado: todos los ejes parten de ''
        despues = _snap('En Prueba', 'Probador Esporádico', 'Sin clasificar')
        cambios = detectar_cambios(None, despues)
        self.assertEqual(len(cambios), 3)
        self.assertTrue(all(c.valor_antes == '' for c in cambios))

    def test_taxo_nuevo_None_no_genera_cambios_si_anterior_tambien_vacio(self):
        # Caso edge raro: pasar de un objeto con todo '' a None debería ser []
        antes = _snap('', '', '')
        self.assertEqual(detectar_cambios(antes, None), [])

    def test_acepta_modelo_django_via_atributos(self):
        # Simula ClienteTaxonomia con MagicMock
        antes_obj = MagicMock(spec=['eje_valor', 'eje_estilo', 'eje_contexto'])
        antes_obj.eje_valor = 'Regular'
        antes_obj.eje_estilo = 'Amante de las Tinas'
        antes_obj.eje_contexto = 'Visitante Pareja'

        despues_dict = _snap('Leal', 'Amante de las Tinas', 'Visitante Pareja')

        cambios = detectar_cambios(antes_obj, despues_dict)
        self.assertEqual(len(cambios), 1)
        self.assertEqual(cambios[0].eje, 'valor')
        self.assertEqual(cambios[0].valor_antes, 'Regular')
        self.assertEqual(cambios[0].valor_despues, 'Leal')

    def test_cambio_es_hashable(self):
        # @dataclass(frozen=True) → permite usar en set
        c1 = Cambio(eje='valor', valor_antes='Dormido', valor_despues='En Prueba')
        c2 = Cambio(eje='valor', valor_antes='Dormido', valor_despues='En Prueba')
        c3 = Cambio(eje='valor', valor_antes='Dormido', valor_despues='Regular')
        s = {c1, c2, c3}
        self.assertEqual(len(s), 2)  # c1==c2

    def test_cambio_str_es_legible(self):
        c = Cambio(eje='valor', valor_antes='Dormido', valor_despues='En Prueba')
        self.assertEqual(str(c), 'valor: Dormido → En Prueba')

    def test_cambio_str_cliente_nuevo_muestra_sin_clasificar(self):
        c = Cambio(eje='valor', valor_antes='', valor_despues='En Prueba')
        self.assertEqual(str(c), 'valor: (sin clasificar) → En Prueba')
