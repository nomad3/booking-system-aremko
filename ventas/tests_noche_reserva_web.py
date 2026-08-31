"""Reservar la Noche de Aguas Calientes desde su landing (2026-08-30).

Cuarta y última experiencia del plan. Es la de precio VARIABLE: la landing
dice «desde $X», así que el armador (construir_servicios_noche) elige la
opción MÁS BARATA disponible — la única elección coherente con esa promesa —
y el precio exacto se muestra en el checkout antes de pagar.

Ejecutar:
    python manage.py test ventas.tests_noche_reserva_web
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from ventas.models import Servicio
from whatsapp_agent.packs import construir_servicios_noche


class ElArmadorDeLaNoche(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cab_barata = Servicio.objects.create(nombre='Cabaña Arrayán',
                                                 precio_base=110000, duracion=60,
                                                 tipo_servicio='cabana')
        cls.cab_cara = Servicio.objects.create(nombre='Cabaña Torre',
                                               precio_base=150000, duracion=60,
                                               tipo_servicio='cabana')
        cls.tina = Servicio.objects.create(nombre='Tina Tronador', precio_base=25000,
                                           duracion=120, tipo_servicio='tina')
        cls.desc = Servicio.objects.create(nombre='Descuento de servicios',
                                           precio_base=-1, duracion=0,
                                           tipo_servicio='otro')

    def _opcion(self, cab, precio_cab, descuento=0):
        total = precio_cab + 50000
        return {
            'cabana': {'servicio_id': cab.pk, 'nombre': cab.nombre,
                       'hora_check_in': '16:00',
                       'hora_check_out': '11:00 del día siguiente',
                       'precio_total': precio_cab},
            'desayuno': None, 'desayuno_incluido': True,
            'tina': {'servicio_id': self.tina.pk, 'nombre': 'Tina Tronador',
                     'hora': '21:30', 'precio_total': 50000},
            'precio_total': total,
            'descuento_pack': descuento,
            'precio_con_descuento': max(0, total - descuento),
            'hay_descuento': descuento > 0,
        }

    def _armar(self, opciones, fecha='2026-09-11'):
        r = {'fecha': fecha, 'personas': 2, 'opciones': opciones, 'nota': ''}
        with patch('whatsapp_agent.packs.disponibilidad_pack_cabana_tina',
                   return_value=r):
            return construir_servicios_noche(fecha)

    def test_elige_la_opcion_MAS_BARATA(self):
        """La landing promete «desde»: vender la cara cuando hay una más
        barata sería mentirle al que hizo la cuenta."""
        r = self._armar([self._opcion(self.cab_cara, 150000),
                         self._opcion(self.cab_barata, 110000)])
        self.assertTrue(r['disponible'])
        self.assertEqual(r['objetivo'], 160000)
        self.assertEqual(r['total'], 160000)
        ids = [x['servicio_id'] for x in r['servicios']]
        self.assertIn(self.cab_barata.pk, ids)
        self.assertNotIn(self.cab_cara.pk, ids)

    def test_el_descuento_dom_jue_baja_el_cobro_y_se_clava(self):
        r = self._armar([self._opcion(self.cab_barata, 110000, descuento=20000)])
        self.assertEqual(r['objetivo'], 140000)
        self.assertEqual(r['total'], 140000)
        linea = [x for x in r['servicios'] if x['servicio_id'] == self.desc.pk]
        self.assertEqual(linea[0]['cantidad_personas'], 20000)

    def test_sin_opciones_no_vende(self):
        r = self._armar([])
        self.assertFalse(r.get('disponible'))

    def test_una_opcion_sin_tina_no_cuenta(self):
        op = self._opcion(self.cab_barata, 110000)
        op.pop('tina')
        r = self._armar([op])
        self.assertFalse(r.get('disponible'))

    def test_integracion_real_una_noche(self):
        """Sin mocks: cabaña y tina con slots reales → el pack de Luna compone
        y el armador entrega el carrito con el total exacto."""
        for s, slots in ((self.cab_barata, {'friday': ['16:00']}),
                         (self.tina, {'friday': ['21:30']})):
            s.publicado_web = True
            s.activo = True
            s.capacidad_minima = 1
            s.capacidad_maxima = 2
            s.slots_disponibles = slots
            s.save()
        r = construir_servicios_noche('2026-09-04')   # viernes
        self.assertTrue(r.get('disponible'), r.get('nota'))
        self.assertEqual(r['total'], r['objetivo'])
        self.assertGreater(r['total'], 0)


class LaVistaDeLaNoche(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cab = Servicio.objects.create(nombre='Cabaña Web', precio_base=110000,
                                          duracion=60, tipo_servicio='cabana')
        cls.tina = Servicio.objects.create(nombre='Tina Web', precio_base=25000,
                                           duracion=120, tipo_servicio='tina')
        cls.url = reverse('noche_reservar')

    def test_arma_el_carrito_cerrado(self):
        armado = {
            'disponible': True, 'fecha': '2026-09-11', 'personas': 2,
            'servicios': [
                {'servicio_id': self.cab.pk, 'fecha': '2026-09-11',
                 'hora': '16:00', 'cantidad_personas': 1},
                {'servicio_id': self.tina.pk, 'fecha': '2026-09-11',
                 'hora': '21:30', 'cantidad_personas': 2},
            ],
            'total': 160000, 'objetivo': 160000,
        }
        with patch('whatsapp_agent.packs.construir_servicios_noche',
                   return_value=armado):
            r = self.client.post(self.url, {'fecha': '2026-09-11'})
        self.assertEqual(r.url, reverse('ventas:checkout'))
        cart = self.client.session['cart']
        self.assertEqual(round(cart['total']), 160000)
        self.assertEqual(cart['paquete_cerrado'], 'noche')

    def test_por_GET_vuelve_a_la_landing(self):
        r = self.client.get(self.url)
        self.assertEqual(r.url, reverse('noche_aguas_calientes_landing'))


class LaLandingDeLaNocheVende(TestCase):
    def _html(self, extra=''):
        return self.client.get(reverse('noche_aguas_calientes_landing') + extra).content.decode()

    def test_vende_primero_con_el_boton_honesto(self):
        html = self._html()
        self.assertIn(reverse('noche_reservar'), html)
        # «Ver precio y reservar»: el precio es variable y el botón no promete
        # un monto que no puede prometer.
        self.assertIn('id="btnReservarNoche"', html)
        self.assertIn('Ver precio y reservar', html)
        self.assertIn('type="date"', html)
        self.assertIn('wa.me/56957902525', html)

    def test_no_ofrece_fechas_pasadas(self):
        from django.utils import timezone as tz

        self.assertIn(f'min="{tz.localdate().isoformat()}"', self._html())

    def test_al_volver_con_motivo_lo_explica(self):
        self.assertIn('no hay cabaña con tina', self._html('?motivo=no_disponible'))
