"""Cotizar a mano: basta el nombre; el correo y el RUT los pone el cliente al aprobar.

Decisión de Jorge (01-09-2026). El caso real: alguien escribe «¿cuánto sale una
noche con tina el sábado?» y solo dejó su teléfono. Exigirle el RUT antes de
decirle el precio es la forma más segura de perder la venta.

La reserva SÍ necesita esos datos —para la boleta y para escribirle—, así que se
piden en la propia cotización, al aprobar: es cuando el cliente se compromete, y
los escribe él en vez de dictarlos por teléfono.

Ejecutar:
    python manage.py test ventas.tests_cotizacion_a_mano
"""
from __future__ import annotations

import datetime

from django.test import TestCase
from django.urls import reverse

from ventas.views.ficha_reserva_view import (_faltan_datos_del_cliente,
                                             token_para_cotizacion)
from whatsapp_agent.models import PropuestaReserva


def _propuesta(cliente, estado='pendiente', dias=2):
    from django.utils import timezone
    return PropuestaReserva.objects.create(
        propuesta_id=f'p-{cliente.get("nombre", "x")}-{estado}',
        idempotency_key=f'k-{cliente.get("nombre", "x")}-{estado}',
        canal='whatsapp', external_id='+56911111111',
        payload={'cliente': cliente, 'servicios': [], 'origen': 'cajon'},
        cliente_data=cliente, servicios=[], total=110000, estado=estado,
        expires_at=timezone.now() + datetime.timedelta(days=dias))


class QueLeFaltaALaCotizacion(TestCase):
    def test_una_cotizacion_a_mano_nace_sin_correo_ni_rut(self):
        p = _propuesta({'nombre': 'Betty Soto'})
        self.assertEqual(sorted(_faltan_datos_del_cliente(p)),
                         ['documento_identidad', 'email'])

    def test_una_de_luna_viene_completa(self):
        p = _propuesta({'nombre': 'Betty Soto', 'email': 'b@correo.cl',
                        'documento_identidad': '12.345.678-9'}, estado='pendiente')
        self.assertEqual(_faltan_datos_del_cliente(p), [])

    def test_un_correo_sin_arroba_cuenta_como_faltante(self):
        # Si entrara así, la creación fallaría más adelante y el cliente vería
        # un botón que no hace nada.
        p = _propuesta({'nombre': 'Betty', 'email': 'betty', 'documento_identidad': '1-9'})
        self.assertEqual(_faltan_datos_del_cliente(p), ['email'])


class LaPaginaDeLaCotizacionPideLoQueFalta(TestCase):
    def test_muestra_los_campos_cuando_faltan(self):
        p = _propuesta({'nombre': 'Betty Soto'})
        url = reverse('ventas:cotizacion_cliente',
                      kwargs={'token': token_para_cotizacion(p.propuesta_id)})
        html = self.client.get(url).content.decode()
        self.assertIn('name="email"', html)
        self.assertIn('name="documento_identidad"', html)

    def test_no_los_muestra_cuando_la_cotizacion_viene_completa(self):
        p = _propuesta({'nombre': 'Betty Soto', 'email': 'b@correo.cl',
                        'documento_identidad': '12.345.678-9'})
        url = reverse('ventas:cotizacion_cliente',
                      kwargs={'token': token_para_cotizacion(p.propuesta_id)})
        html = self.client.get(url).content.decode()
        self.assertNotIn('name="documento_identidad"', html)


class AlAprobarSeGuardanLosDatos(TestCase):
    def _aprobar(self, propuesta, **datos):
        url = reverse('ventas:aprobar_cotizacion',
                      kwargs={'token': token_para_cotizacion(propuesta.propuesta_id)})
        return self.client.post(url, datos)

    def test_sin_correo_no_avanza_y_lo_dice(self):
        p = _propuesta({'nombre': 'Betty Soto'})
        r = self._aprobar(p, documento_identidad='12.345.678-9')
        self.assertEqual(r.status_code, 400)
        self.assertIn('correo', r.content.decode().lower())
        p.refresh_from_db()
        self.assertEqual(p.estado, 'pendiente')

    def test_sin_rut_tampoco(self):
        p = _propuesta({'nombre': 'Betty Soto'})
        r = self._aprobar(p, email='betty@correo.cl')
        self.assertEqual(r.status_code, 400)
        self.assertIn('RUT', r.content.decode())

    def test_con_los_datos_quedan_guardados_en_la_propuesta(self):
        # No se pierde lo escrito aunque la creación de la reserva falle
        # después por otra razón: el dato del cliente ya es suyo.
        p = _propuesta({'nombre': 'Betty Soto'})
        self._aprobar(p, email='betty@correo.cl', documento_identidad='12.345.678-9')
        p.refresh_from_db()
        self.assertEqual(p.payload['cliente']['email'], 'betty@correo.cl')
        self.assertEqual(p.cliente_data['documento_identidad'], '12.345.678-9')

    def test_lo_ya_escrito_se_devuelve_al_reintentar(self):
        # Si el RUT falta, no se le borra el correo que ya había escrito.
        p = _propuesta({'nombre': 'Betty Soto'})
        r = self._aprobar(p, email='betty@correo.cl')
        self.assertIn('betty@correo.cl', r.content.decode())
