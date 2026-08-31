"""Reservar y pagar el Refugio Aremko desde su landing (2026-08-30).

Segunda experiencia del plan (Ritual → Refugio → Pausa → Noche). Decisión de
Jorge: se deja de lado la captura de leads; la landing VENDE como prioridad y
WhatsApp queda de segunda opción. El constructor es el de Luna
(construir_servicios_refugio): 2 noches, misma cabaña, $290.000 plano.

Ejecutar:
    python manage.py test ventas.tests_refugio_reserva_web
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from ventas.models import Servicio


class ReservarElRefugio(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cab = Servicio.objects.create(nombre='Cabaña Torre', precio_base=120000,
                                          duracion=60, tipo_servicio='cabana')
        cls.tina = Servicio.objects.create(nombre='Tina Nocturna', precio_base=25000,
                                           duracion=120, tipo_servicio='tina')
        cls.url = reverse('refugio_reservar')

    def _armado(self, objetivo=290000, **extra):
        """La misma cabaña DOS noches (120.000×2) + tina 25.000×2 = 290.000."""
        base = {
            'disponible': True,
            'fecha': '2026-09-11',
            'fecha_salida': '2026-09-13',
            'personas': 2,
            'noches': 2,
            'servicios': [
                {'servicio_id': self.cab.id, 'fecha': '2026-09-11',
                 'hora': '16:00', 'cantidad_personas': 1},
                {'servicio_id': self.cab.id, 'fecha': '2026-09-12',
                 'hora': '16:00', 'cantidad_personas': 1},
                {'servicio_id': self.tina.id, 'fecha': '2026-09-11',
                 'hora': '20:30', 'cantidad_personas': 2},
            ],
            'total': objetivo,
            'objetivo': objetivo,
        }
        base.update(extra)
        return base

    def _post(self, fecha='2026-09-11', armado=None):
        with patch('whatsapp_agent.packs.construir_servicios_refugio',
                   return_value=armado if armado is not None else self._armado()):
            return self.client.post(self.url, {'fecha': fecha})

    def test_arma_las_dos_noches_contra_el_objetivo(self):
        r = self._post()
        self.assertEqual(r.url, reverse('ventas:checkout'))
        cart = self.client.session['cart']
        self.assertEqual(round(cart['total']), 290000)
        self.assertEqual(cart['paquete_cerrado'], 'refugio')
        # Dos líneas de cabaña, una por noche: la forma del Refugio.
        noches = [i for i in cart['servicios'] if i['tipo_servicio'] == 'cabana']
        self.assertEqual(len(noches), 2)
        self.assertNotEqual(noches[0]['fecha'], noches[1]['fecha'])

    def test_si_el_total_no_calza_NO_se_paga(self):
        malo = self._armado()
        malo['servicios'] = malo['servicios'][:2]   # faltó la tina: suma 240.000
        r = self._post(armado=malo)
        self.assertIn('motivo=precio', r.url)
        self.assertNotIn('cart', self.client.session)

    def test_sin_cupo_vuelve_explicando(self):
        r = self._post(armado={'disponible': False, 'fecha': '2026-09-11',
                               'nota': 'sin cabañas para 2 noches seguidas'})
        self.assertIn('motivo=no_disponible', r.url)

    def test_fecha_pasada_se_rechaza(self):
        r = self._post(fecha='2025-01-01')
        self.assertIn('motivo=no_disponible', r.url)
        self.assertNotIn('cart', self.client.session)

    def test_por_GET_vuelve_a_la_landing(self):
        # La landing exige RefugioConfig activo; el redirect no la dibuja,
        # así que basta el destino.
        r = self.client.get(self.url)
        self.assertEqual(r.url, reverse('refugio_landing'))


class LaLandingDelRefugioVende(TestCase):
    @classmethod
    def setUpTestData(cls):
        from ventas.models import RefugioConfig

        config = RefugioConfig.get_solo()
        config.activo = True
        config.save()

    def _html(self, extra=''):
        r = self.client.get(reverse('refugio_landing') + extra)
        assert r.status_code == 200, f'la landing no se dibujó: {r.status_code}'
        return r.content.decode()

    def test_vende_primero_y_whatsapp_segundo(self):
        html = self._html()
        self.assertIn(reverse('refugio_reservar'), html)
        # El botón CON precio: solo existe en el formulario. El texto a secas
        # también vive en el hero, y con esa vara la prueba no mordía — quitar
        # el botón la dejaba verde (falso verde cazado el 30-08).
        self.assertIn('Reservar y pagar $290.000', html)
        self.assertIn('type="date"', html)
        self.assertIn('wa.me/56957902525', html)   # segunda opción, sigue

    def test_el_formulario_de_leads_ya_no_esta(self):
        """La decisión: dejamos de lado la captura de leads. Si el formulario
        viejo reaparece, la landing vuelve a repartir su prioridad."""
        self.assertNotIn('id="refugio-form"', self._html())

    def test_no_ofrece_fechas_pasadas(self):
        from django.utils import timezone as tz

        self.assertIn(f'min="{tz.localdate().isoformat()}"', self._html())

    def test_al_volver_con_motivo_lo_explica(self):
        html = self._html('?motivo=no_disponible&fecha=2026-09-11')
        self.assertIn('ya no están disponibles', html)
