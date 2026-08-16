# -*- coding: utf-8 -*-
"""H-108: las gift cards publicadas entran al modal «Alternativas de horario».

Qué fija esta suite y por qué:

- El catálogo que ve la bandeja es EL MISMO que vende Luna y pinta la vitrina
  (`activo=True`): activar una experiencia en el admin la publica en los tres
  lados sin deploy. Una inactiva no aparece; una sin precio alguno se omite.
- `fecha` y `personas` se ignoran para este tipo — y el endpoint deja de
  exigir `fecha` SOLO para giftcard: los tipos con agenda siguen en 400.
- El texto que se le pega al cliente dice siempre «Gift Card» (regla de Jorge
  2026-08-13: nunca «carta») e incluye el argumento de venta del año de
  vigencia.

Correr con:
  docker compose run --rm web python manage.py test \
      whatsapp_agent.tests.test_h108_giftcards_en_alternativas \
      --settings=aremko_project.test_settings
"""
from django.test import TestCase, override_settings

from ventas.models import GiftCardExperiencia
from whatsapp_agent.alternativas import construir_alternativas


def _experiencia(id_exp, nombre, **extra):
    """Experiencia mínima válida; el resto de los campos vía kwargs."""
    campos = dict(
        id_experiencia=id_exp,
        categoria='masajes',
        nombre=nombre,
        descripcion='Dos masajes en la misma sala.',
        descripcion_giftcard='Detalle largo para la carta impresa.',
        imagen='giftcards/experiencias/test.jpg',
        activo=True,
    )
    campos.update(extra)
    return GiftCardExperiencia.objects.create(**campos)


class GiftcardBuilderTests(TestCase):
    """construir_alternativas('giftcard', ...) — el builder puro."""

    def setUp(self):
        _experiencia('masaje_dos', 'Masaje para Dos', monto_fijo=80000, orden=1)
        _experiencia('tarjeta_valor', 'Tarjeta Aremko', categoria='valor',
                     descripcion='Monto libre para cualquier servicio.',
                     montos_sugeridos=[30000, 50000, 75000], orden=1)
        _experiencia('sin_precio', 'Experiencia sin precio', orden=2)
        _experiencia('apagada', 'Experiencia Apagada', monto_fijo=99000,
                     activo=False, orden=3)

    def test_solo_el_catalogo_publicado_y_con_precio(self):
        res = construir_alternativas('giftcard', None, 2)
        self.assertNotIn('error', res)
        self.assertEqual(res['nombre_experiencia'], 'Gift Card')
        self.assertIsNone(res['fecha'])
        titulos = [a['titulo'] for a in res['alternativas']]
        # La inactiva no está (activo=True es el filtro del catálogo) y la sin
        # precio se omite: un botón sin precio no ofrece nada vendible.
        self.assertEqual(len(titulos), 2)
        self.assertIn('Masaje para Dos', titulos)
        self.assertNotIn('Experiencia Apagada', titulos)

    def test_monto_fijo(self):
        res = construir_alternativas('giftcard', None, 2)
        alt = next(a for a in res['alternativas']
                   if a['titulo'] == 'Masaje para Dos')
        self.assertEqual(alt['precio_total'], 80000)
        self.assertEqual(alt['precio_con_descuento'], 80000)
        self.assertFalse(alt['hay_descuento'])
        self.assertEqual(alt['itinerario'], [])  # nada que agendar
        self.assertIn('Gift Card «Masaje para Dos»', alt['texto_sugerido'])
        self.assertIn('$80.000', alt['texto_sugerido'])
        self.assertIn('1 año', alt['texto_sugerido'])

    def test_tarjeta_de_valor_usa_el_minimo_y_lista_los_montos(self):
        res = construir_alternativas('giftcard', None, 2)
        alt = next(a for a in res['alternativas']
                   if a['titulo'].startswith('Tarjeta Aremko'))
        self.assertIn('monto a elección', alt['titulo'])
        self.assertEqual(alt['precio_total'], 30000)  # el mínimo sugerido
        for monto in ('$30.000', '$50.000', '$75.000'):
            self.assertIn(monto, alt['texto_sugerido'])

    def test_fecha_y_personas_se_ignoran(self):
        con_fecha = construir_alternativas('giftcard', '2026-12-25', 4)
        sin_fecha = construir_alternativas('giftcard', None, 2)
        self.assertEqual(con_fecha['alternativas'], sin_fecha['alternativas'])

    def test_dice_gift_card_nunca_carta(self):
        # Regla de naming de Jorge (2026-08-13): el cliente lee «Gift Card».
        for alt in construir_alternativas('giftcard', None, 2)['alternativas']:
            texto = alt['texto_sugerido'].lower()
            self.assertIn('gift card', texto)
            self.assertNotIn('carta', texto)


@override_settings(LUNA_API_KEY='clave-de-test')
class GiftcardEndpointTests(TestCase):
    """GET /api/luna/experiencias/alternativas/ — la regla de la fecha."""

    URL = '/api/luna/experiencias/alternativas/'

    def _get(self, **params):
        return self.client.get(self.URL, params,
                               HTTP_X_API_KEY='clave-de-test')

    def test_giftcard_sin_fecha_responde_200(self):
        _experiencia('masaje_dos', 'Masaje para Dos', monto_fijo=80000)
        resp = self._get(tipo='giftcard')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['tipo'], 'giftcard')
        self.assertIsNone(data['fecha'])
        self.assertEqual(len(data['alternativas']), 1)

    def test_tipos_con_agenda_siguen_exigiendo_fecha(self):
        resp = self._get(tipo='tina_sola')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('fecha', resp.json()['error'])

    def test_tipo_invalido_lista_giftcard_entre_los_validos(self):
        resp = self._get(tipo='no_existe', fecha='2026-12-25')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('giftcard', resp.json()['error'])
