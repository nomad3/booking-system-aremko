"""Reservar y pagar el Ritual del Río desde su landing (2026-08-30).

Decisión de Jorge: las landings venden primero; WhatsApp es la segunda opción.
El camino reutiliza el constructor de Luna (construir_servicios_ritual) y el
blindaje del día — con una diferencia: la integridad no es un monto fijo sino
el `objetivo` que declara el constructor ($210.000 dom-jue / $240.000 vie-sáb).

Ejecutar:
    python manage.py test ventas.tests_ritual_reserva_web
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from ventas.models import Servicio


class ReservarElRitual(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cab = Servicio.objects.create(nombre='Cabaña Torre', precio_base=150000,
                                          duracion=60, tipo_servicio='cabana')
        cls.tina = Servicio.objects.create(nombre='Tina Nocturna', precio_base=30000,
                                           duracion=120, tipo_servicio='tina')
        cls.url = reverse('ritual_reservar')

    def _armado(self, objetivo=210000, **extra):
        """150.000×1 + 30.000×2 = 210.000 exactos (domingo a jueves)."""
        base = {
            'disponible': True,
            'fecha': '2026-09-06',
            'personas': 2,
            'servicios': [
                {'servicio_id': self.cab.id, 'fecha': '2026-09-06',
                 'hora': '16:00', 'cantidad_personas': 1},
                {'servicio_id': self.tina.id, 'fecha': '2026-09-06',
                 'hora': '20:30', 'cantidad_personas': 2},
            ],
            'total': objetivo,
            'objetivo': objetivo,
        }
        base.update(extra)
        return base

    def _post(self, fecha='2026-09-06', armado=None):
        with patch('whatsapp_agent.packs.construir_servicios_ritual',
                   return_value=armado if armado is not None else self._armado()):
            return self.client.post(self.url, {'fecha': fecha})

    def test_arma_el_carrito_contra_el_objetivo_del_constructor(self):
        r = self._post()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse('ventas:checkout'))
        cart = self.client.session['cart']
        self.assertEqual(round(cart['total']), 210000)
        self.assertEqual(cart['paquete_cerrado'], 'ritual')
        # El Ritual duerme ahí: NO lleva bloqueo de noche previa (eso es del día).
        self.assertNotIn('dia_bloqueo', cart)

    def test_si_el_total_no_calza_con_el_objetivo_NO_se_paga(self):
        """El precio del catálogo cambió bajo los pies: preferible perder la
        venta a cobrar un monto que nadie prometió."""
        malo = self._armado()
        malo['objetivo'] = 240000   # viernes, pero los servicios suman 210.000
        r = self._post(armado=malo)
        self.assertIn('motivo=precio', r.url)
        self.assertNotIn('cart', self.client.session)

    def test_sin_objetivo_declarado_tampoco_se_paga(self):
        r = self._post(armado=self._armado(objetivo=0))
        self.assertIn('motivo=precio', r.url)
        self.assertNotIn('cart', self.client.session)

    def test_una_noche_sin_cupo_vuelve_explicando(self):
        r = self._post(armado={'disponible': False, 'fecha': '2026-09-06',
                               'nota': 'sin cabañas esa noche'})
        self.assertIn('motivo=no_disponible', r.url)
        self.assertIn('fecha=2026-09-06', r.url)

    def test_una_fecha_pasada_se_rechaza(self):
        r = self._post(fecha='2025-01-01')
        self.assertIn('motivo=no_disponible', r.url)
        self.assertNotIn('cart', self.client.session)

    def test_sin_fecha_no_inventa(self):
        r = self.client.post(self.url, {})
        self.assertIn('motivo=sin_fecha', r.url)

    def test_por_GET_no_arma_nada(self):
        r = self.client.get(self.url)
        self.assertEqual(r.url, reverse('ritual_rio_landing'))
        self.assertNotIn('cart', self.client.session)


class LaLandingDelRitualVende(TestCase):
    def _html(self, extra=''):
        return self.client.get(reverse('ritual_rio_landing') + extra).content.decode()

    def test_ofrece_el_formulario_de_pago_primero_y_whatsapp_segundo(self):
        html = self._html()
        self.assertIn(reverse('ritual_reservar'), html)
        self.assertIn('Reservar y pagar', html)
        self.assertIn('csrfmiddlewaretoken', html)
        self.assertIn('type="date"', html)
        # WhatsApp sigue, como segunda opción — la decisión de uniformar.
        self.assertIn('wa.me/56957902525', html)

    def test_muestra_los_dos_precios_del_objetivo(self):
        html = self._html()
        self.assertIn('210.000', html)
        self.assertIn('240.000', html)

    def test_el_calendario_no_ofrece_fechas_pasadas(self):
        from django.utils import timezone as tz

        self.assertIn(f'min="{tz.localdate().isoformat()}"', self._html())

    def test_al_volver_con_motivo_lo_explica(self):
        html = self._html('?motivo=no_disponible&fecha=2026-09-06')
        self.assertIn('ya no está disponible', html)
