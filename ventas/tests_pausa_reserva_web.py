"""Reservar y pagar la Pausa junto al río desde su landing (2026-08-30).

Tercera experiencia del plan. La Pausa es la primera con ARMADOR NUEVO
(construir_servicios_pausa): reutiliza el cotizador de Luna
(disponibilidad_pack_tina_masaje) y elige la alternativa clásica cuyo precio
cobrado sea EXACTAMENTE el publicado en la landing ($110.000 dom-jue /
$130.000 vie-sáb). Si ninguna cuadra, no vende: la web no puede cobrar
distinto de lo que la página promete.

Ejecutar:
    python manage.py test ventas.tests_pausa_reserva_web
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from ventas.models import Servicio
from whatsapp_agent.packs import construir_servicios_pausa


def _candidato(tina_id, masaje_id, precio_tina=50000, precio_masaje=80000,
               descuento=0, etiqueta='sin hidromasaje'):
    total = precio_tina + precio_masaje
    return {
        'etiqueta': etiqueta,
        'tina': {'servicio_id': tina_id, 'nombre': 'Tina Tronador',
                 'hora': '15:30', 'duracion_texto': '2 h',
                 'precio_total': precio_tina, 'precio_por_persona': precio_tina // 2},
        'masaje': {'servicio_id': masaje_id, 'nombre': 'Masaje Relajación',
                   'hora': '14:15', 'cantidad': 2, 'precio_total': precio_masaje},
        'orden': 'masaje antes de la tina',
        'clustering': False,
        'precio_total': total,
        'descuento_pack': descuento,
        'precio_con_descuento': max(0, total - descuento),
        'hay_descuento': descuento > 0,
    }


class ElArmadorDeLaPausa(TestCase):
    """El armador contra su contrato: elegir SOLO lo que cuadra con la tabla."""

    @classmethod
    def setUpTestData(cls):
        cls.tina = Servicio.objects.create(nombre='Tina Tronador', precio_base=25000,
                                           duracion=120, tipo_servicio='tina')
        cls.masaje = Servicio.objects.create(nombre='Masaje Relajación',
                                             precio_base=40000, duracion=50,
                                             tipo_servicio='masaje')
        cls.desc = Servicio.objects.create(nombre='Descuento de servicios',
                                           precio_base=-1, duracion=0,
                                           tipo_servicio='otro')

    def _armar(self, fecha, candidatos):
        r = {'fecha': fecha, 'personas': 2, 'opciones': candidatos[:2],
             'alternativas': candidatos, 'nota': '', 'nota_upsell': ''}
        with patch('whatsapp_agent.packs.disponibilidad_pack_tina_masaje',
                   return_value=r):
            return construir_servicios_pausa(fecha)

    def test_viernes_130_sin_descuento(self):
        """25.000×2 + 40.000×2 = 130.000 exactos: el precio de finde."""
        r = self._armar('2026-09-04',   # viernes
                        [_candidato(self.tina.pk, self.masaje.pk)])
        self.assertTrue(r['disponible'])
        self.assertEqual(r['objetivo'], 130000)
        self.assertEqual(r['total'], 130000)
        self.assertEqual(len(r['servicios']), 2)   # sin línea de descuento

    def test_jueves_110_con_descuento_de_pack(self):
        """El pack dom-jue rebaja 20.000: el armador agrega la línea de
        descuento para que el carrito sume exactamente 110.000."""
        r = self._armar('2026-09-03',   # jueves
                        [_candidato(self.tina.pk, self.masaje.pk, descuento=20000)])
        self.assertTrue(r['disponible'])
        self.assertEqual(r['objetivo'], 110000)
        self.assertEqual(r['total'], 110000)
        linea_desc = [x for x in r['servicios'] if x['servicio_id'] == self.desc.pk]
        self.assertEqual(len(linea_desc), 1)
        self.assertEqual(linea_desc[0]['cantidad_personas'], 20000)

    def test_si_ninguna_alternativa_cuadra_NO_vende(self):
        """Una tina más cara (60k) el jueves sin pack: cobraría 140.000 y la
        página promete 110.000. El armador prefiere no vender."""
        r = self._armar('2026-09-03',
                        [_candidato(self.tina.pk, self.masaje.pk,
                                    precio_tina=60000)])
        self.assertFalse(r.get('disponible'))
        self.assertIn('precio publicado', r['nota'])

    def test_elige_la_que_cuadra_aunque_no_sea_la_primera(self):
        """Con varias alternativas, la vara es el precio publicado, no el
        orden: la cara se salta y se toma la que cuadra."""
        cara = _candidato(self.tina.pk, self.masaje.pk, precio_tina=60000)
        justa = _candidato(self.tina.pk, self.masaje.pk)
        r = self._armar('2026-09-04', [cara, justa])
        self.assertTrue(r['disponible'])
        self.assertEqual(r['total'], 130000)

    def test_la_opcion_con_hidromasaje_no_se_toma(self):
        hidro = _candidato(self.tina.pk, self.masaje.pk, etiqueta='con hidromasaje')
        r = self._armar('2026-09-04', [hidro])
        self.assertFalse(r.get('disponible'))

    def test_integracion_real_un_viernes(self):
        """Sin mocks: fixtures con slots de viernes y el cotizador REAL de
        Luna. El armador debe componer la Pausa de $130.000 de punta a punta."""
        self.tina.publicado_web = True
        self.tina.activo = True
        self.tina.capacidad_minima = 1
        self.tina.capacidad_maxima = 4
        self.tina.slots_disponibles = {'friday': ['15:30']}
        self.tina.save()
        self.masaje.publicado_web = True
        self.masaje.activo = True
        self.masaje.capacidad_minima = 1
        self.masaje.capacidad_maxima = 4
        self.masaje.slots_disponibles = {'friday': ['14:15']}
        self.masaje.save()

        r = construir_servicios_pausa('2026-09-04')
        self.assertTrue(r.get('disponible'), r.get('nota'))
        self.assertEqual(r['total'], 130000)
        self.assertEqual(r['objetivo'], 130000)


class LaLandingDeLaPausaVende(TestCase):
    def _html(self, extra=''):
        return self.client.get(reverse('pausa_landing') + extra).content.decode()

    def test_vende_primero_y_whatsapp_segundo(self):
        html = self._html()
        self.assertIn(reverse('pausa_reservar'), html)
        self.assertIn('id="btnReservarPausa"', html)
        self.assertIn('110.000', html)
        self.assertIn('130.000', html)
        self.assertIn('type="date"', html)
        self.assertIn('wa.me/56957902525', html)

    def test_no_ofrece_fechas_pasadas(self):
        from django.utils import timezone as tz

        self.assertIn(f'min="{tz.localdate().isoformat()}"', self._html())

    def test_al_volver_con_motivo_lo_explica(self):
        self.assertIn('precio publicado', self._html('?motivo=no_disponible'))


class LaVistaDeLaPausa(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tina = Servicio.objects.create(nombre='Tina Web', precio_base=25000,
                                           duracion=120, tipo_servicio='tina')
        cls.masaje = Servicio.objects.create(nombre='Masaje Web', precio_base=40000,
                                             duracion=50, tipo_servicio='masaje')
        cls.url = reverse('pausa_reservar')

    def test_arma_el_carrito_cerrado(self):
        armado = {
            'disponible': True, 'fecha': '2026-09-04', 'personas': 2,
            'servicios': [
                {'servicio_id': cls_t, 'fecha': '2026-09-04', 'hora': '15:30',
                 'cantidad_personas': 2} for cls_t in (self.tina.pk,)
            ] + [
                {'servicio_id': self.masaje.pk, 'fecha': '2026-09-04',
                 'hora': '14:15', 'cantidad_personas': 2},
            ],
            'total': 130000, 'objetivo': 130000,
        }
        with patch('whatsapp_agent.packs.construir_servicios_pausa',
                   return_value=armado):
            r = self.client.post(self.url, {'fecha': '2026-09-04'})
        self.assertEqual(r.url, reverse('ventas:checkout'))
        cart = self.client.session['cart']
        self.assertEqual(round(cart['total']), 130000)
        self.assertEqual(cart['paquete_cerrado'], 'pausa')

    def test_por_GET_vuelve_a_la_landing(self):
        r = self.client.get(self.url)
        self.assertEqual(r.url, reverse('pausa_landing'))
