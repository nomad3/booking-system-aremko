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
                        'documento_identidad': '12.345.678-5'}, estado='pendiente')
        self.assertEqual(_faltan_datos_del_cliente(p), [])

    def test_un_correo_sin_arroba_cuenta_como_faltante(self):
        # Si entrara así, la creación fallaría más adelante y el cliente vería
        # un botón que no hace nada.
        p = _propuesta({'nombre': 'Betty', 'email': 'betty',
                        'documento_identidad': '11.111.111-1'})
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
                        'documento_identidad': '12.345.678-5'})
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
        r = self._aprobar(p, documento_identidad='12.345.678-5')
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
        self._aprobar(p, email='betty@correo.cl', documento_identidad='12.345.678-5')
        p.refresh_from_db()
        self.assertEqual(p.payload['cliente']['email'], 'betty@correo.cl')
        self.assertEqual(p.cliente_data['documento_identidad'], '12.345.678-5')

    def test_lo_ya_escrito_se_devuelve_al_reintentar(self):
        # Si el RUT falta, no se le borra el correo que ya había escrito.
        p = _propuesta({'nombre': 'Betty Soto'})
        r = self._aprobar(p, email='betty@correo.cl')
        self.assertIn('betty@correo.cl', r.content.decode())


class UnDatoMalEscritoSePideDeNuevo(TestCase):
    """23-09-2026: una cotización con el RUT de ejemplo (12345678-9, dígito
    verificador malo) llegó al botón Aprobar y el cliente vio «Datos de cliente
    inválidos» sin ningún campo que corregir. Un dato mal escrito cuenta igual
    que uno que falta: se muestra, con el motivo, y se pide de nuevo."""

    RUT_MALO = '12345678-9'      # el dígito correcto es 5
    RUT_BUENO = '12.345.678-5'

    def _url(self, propuesta, vista='cotizacion_cliente'):
        return reverse(f'ventas:{vista}',
                       kwargs={'token': token_para_cotizacion(propuesta.propuesta_id)})

    def test_un_rut_con_digito_malo_cuenta_como_por_corregir(self):
        p = _propuesta({'nombre': 'Betty Soto', 'email': 'b@correo.cl',
                        'documento_identidad': self.RUT_MALO})
        self.assertEqual(_faltan_datos_del_cliente(p), ['documento_identidad'])

    def test_un_correo_sin_dominio_tambien(self):
        p = _propuesta({'nombre': 'Betty Soto', 'email': 'betty@correo',
                        'documento_identidad': self.RUT_BUENO})
        self.assertEqual(_faltan_datos_del_cliente(p), ['email'])

    def test_al_abrir_el_link_se_ve_el_campo_con_lo_que_tenemos_y_el_motivo(self):
        p = _propuesta({'nombre': 'Betty Soto', 'email': 'b@correo.cl',
                        'documento_identidad': self.RUT_MALO})
        html = self.client.get(self._url(p)).content.decode()
        self.assertIn('name="documento_identidad"', html)
        self.assertIn(f'value="{self.RUT_MALO}"', html)
        self.assertIn('dígito verificador no calza', html)
        self.assertNotIn('name="email"', html, 'el correo está bien: no se pide')

    def test_aprobar_con_el_mismo_rut_malo_no_avanza_y_explica(self):
        p = _propuesta({'nombre': 'Betty Soto', 'email': 'b@correo.cl',
                        'documento_identidad': self.RUT_MALO})
        r = self.client.post(self._url(p, 'aprobar_cotizacion'),
                             {'documento_identidad': self.RUT_MALO})
        self.assertEqual(r.status_code, 400)
        html = r.content.decode()
        self.assertIn('dígito verificador no calza', html)
        self.assertIn('name="documento_identidad"', html)
        self.assertNotIn('Datos de cliente inválidos', html)
        p.refresh_from_db()
        self.assertEqual(p.cliente_data['documento_identidad'], self.RUT_MALO)

    def test_un_rut_sin_formato_lo_dice_distinto(self):
        p = _propuesta({'nombre': 'Betty Soto', 'email': 'b@correo.cl',
                        'documento_identidad': '1234'})
        html = self.client.get(self._url(p)).content.decode()
        self.assertIn('no tiene el formato', html)

    def test_el_rut_corregido_queda_guardado_y_reemplaza_al_malo(self):
        p = _propuesta({'nombre': 'Betty Soto', 'email': 'b@correo.cl',
                        'documento_identidad': self.RUT_MALO})
        self.client.post(self._url(p, 'aprobar_cotizacion'),
                         {'documento_identidad': self.RUT_BUENO})
        p.refresh_from_db()
        self.assertEqual(p.cliente_data['documento_identidad'], self.RUT_BUENO)
        self.assertEqual(p.payload['cliente']['documento_identidad'], self.RUT_BUENO)

    def test_un_correo_mal_escrito_al_aprobar_se_rechaza_con_motivo(self):
        p = _propuesta({'nombre': 'Betty Soto'})
        r = self.client.post(self._url(p, 'aprobar_cotizacion'),
                             {'email': 'betty@correo', 'documento_identidad': self.RUT_BUENO})
        self.assertEqual(r.status_code, 400)
        html = r.content.decode()
        self.assertIn('no parece válido', html)
        self.assertIn('value="betty@correo"', html, 'lo escrito se devuelve para corregirlo')


class SiLaCreacionRechazaElClienteEntiende(TestCase):
    """Cuando `crear_reserva` responde validation_error, el cliente no debe ver
    «Datos de cliente inválidos»: o se le muestra el campo a corregir, o se le
    dice que lo contactamos."""

    def _aprobar(self, propuesta):
        url = reverse('ventas:aprobar_cotizacion',
                      kwargs={'token': token_para_cotizacion(propuesta.propuesta_id)})
        return self.client.post(url, {})

    def test_un_rechazo_que_el_cliente_no_puede_arreglar_se_dice_en_su_idioma(self):
        from unittest import mock
        from rest_framework.response import Response
        p = _propuesta({'nombre': 'Betty Soto', 'email': 'b@correo.cl',
                        'telefono': '12', 'documento_identidad': '12.345.678-5'})
        rechazo = Response({'success': False, 'error': 'validation_error',
                            'errores': [{'campo': 'telefono', 'mensaje': 'Teléfono inválido'}],
                            'mensaje': 'Datos de cliente inválidos'}, status=400)
        with mock.patch('ventas.views.luna_api_views.crear_reserva', return_value=rechazo):
            r = self._aprobar(p)
        html = r.content.decode()
        self.assertEqual(r.status_code, 400)
        self.assertNotIn('Datos de cliente inválidos', html)
        self.assertIn('Te contactamos', html)

    def test_otros_errores_siguen_mostrando_su_mensaje(self):
        from unittest import mock
        from rest_framework.response import Response
        p = _propuesta({'nombre': 'Betty Soto', 'email': 'b@correo.cl',
                        'documento_identidad': '12.345.678-5'})
        rechazo = Response({'success': False, 'error': 'availability_error',
                            'mensaje': 'Uno o más servicios no están disponibles'}, status=400)
        with mock.patch('ventas.views.luna_api_views.crear_reserva', return_value=rechazo):
            r = self._aprobar(p)
        self.assertIn('no están disponibles', r.content.decode())
