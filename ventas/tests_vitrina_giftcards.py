# -*- coding: utf-8 -*-
"""La vitrina de /giftcards/ se cura desde el admin, no desde el código.

Hasta el 2026-08-12 la lista de experiencias mostradas era una constante en
giftcard_views.py (`IDS_INSIGNIA`). Jorge activó los masajes en el admin y no
aparecieron en la web — mientras Luna, que lee todas las activas, sí los
ofrecía. Dos canales, dos criterios. Ahora manda `destacada_web`.
"""
from django.test import TestCase
from django.urls import reverse

from ventas.models import GiftCardExperiencia


def _exp(id_exp, nombre, precio=50000, activo=True, destacada=False, orden=0):
    return GiftCardExperiencia.objects.create(
        id_experiencia=id_exp, categoria='packs', nombre=nombre,
        descripcion='desc', descripcion_giftcard='detalle',
        imagen='giftcards/x.jpg', monto_fijo=precio, activo=activo,
        destacada_web=destacada, orden=orden)


class VitrinaGiftcardsTest(TestCase):

    def _vitrina(self):
        r = self.client.get(reverse('ventas:giftcard_menu'))
        self.assertEqual(r.status_code, 200)
        return r

    def test_solo_salen_las_destacadas(self):
        _exp('pausa', 'Pausa junto al río', destacada=True, orden=1)
        _exp('velada_dulce', 'Velada Sorpresa Dulce', destacada=False)
        r = self._vitrina()
        ids = [e['id'] for e in r.context['experiencias_insignia']]
        self.assertEqual(ids, ['pausa'])

    def test_marcar_un_masaje_lo_publica_sin_deploy(self):
        """El caso exacto: activarlo no bastaba porque la lista era fija."""
        _exp('pausa', 'Pausa junto al río', destacada=True)
        masaje = _exp('masaje_pareja', 'Masaje para Dos', precio=80000)
        self.assertNotIn('masaje_pareja',
                         [e['id'] for e in self._vitrina().context['experiencias_insignia']])

        GiftCardExperiencia.objects.filter(pk=masaje.pk).update(destacada_web=True)
        self.assertIn('masaje_pareja',
                      [e['id'] for e in self._vitrina().context['experiencias_insignia']])

    def test_una_inactiva_no_sale_aunque_este_destacada(self):
        """`activo` sigue mandando: destacar no resucita lo dado de baja."""
        _exp('pausa', 'Pausa junto al río', destacada=True)
        _exp('vieja', 'Ya no va', activo=False, destacada=True)
        ids = [e['id'] for e in self._vitrina().context['experiencias_insignia']]
        self.assertNotIn('vieja', ids)

    def test_sin_ninguna_destacada_la_vitrina_no_queda_en_blanco(self):
        """Un destildado accidental no puede dejar la página vacía: cae a
        todas las activas."""
        _exp('pausa', 'Pausa junto al río')
        _exp('ritual', 'Ritual del Río')
        ids = [e['id'] for e in self._vitrina().context['experiencias_insignia']]
        self.assertEqual(sorted(ids), ['pausa', 'ritual'])

    def test_el_orden_lo_decide_el_campo_orden(self):
        _exp('caro', 'Refugio', precio=290000, destacada=True, orden=3)
        _exp('barato', 'Tina para dos', precio=50000, destacada=True, orden=1)
        ids = [e['id'] for e in self._vitrina().context['experiencias_insignia']]
        self.assertEqual(ids, ['barato', 'caro'])
