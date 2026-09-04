"""Fase 3: las boletas de clientes fuera de la ventana, por plantilla.

Las de clientes que escribieron hace poco ya salieron con el PDF adjunto y
gratis (fase 2). Estas se pagan, así que la regla que más importa es
**agrupar**: un cliente con tres boletas de la misma visita recibe UN
mensaje, no tres. El enlace va a su Pase, donde están las tres.

Ejecutar:
    python manage.py test facturacion.tests_boletas_pendientes
"""
from __future__ import annotations

import datetime
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from facturacion.models import BoletaElectronica
from ventas.models import Cliente, VentaReserva, WhatsAppMessage


def _correr(**opts):
    out = StringIO()
    call_command('enviar_boletas_pendientes', stdout=out, **opts)
    return out.getvalue()


def _ok():
    r = MagicMock(); r.status_code = 200; return r


class AgrupaPorVisita(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Marta Soto',
                                              telefono='+56912345678')
        self.venta = VentaReserva.objects.create(cliente=self.cliente)

    def _boleta(self, folio, venta=None):
        return BoletaElectronica.objects.create(
            pago=None, venta_reserva=venta or self.venta, ambiente='produccion',
            folio=folio, estado='aceptada', monto_total=10000,
            monto_neto=8403, monto_iva=1597, emitida_at=timezone.now())

    def test_tres_boletas_de_una_visita_son_UN_mensaje(self):
        # El caso de Jorge: transferencia + café + café. Tres plantillas
        # serían tres cobros de Meta por decir lo mismo.
        for f in (10, 11, 12):
            self._boleta(f)
        with patch('requests.post', return_value=_ok()) as post:
            _correr()
        self.assertEqual(post.call_count, 1)

    def test_marca_las_tres_como_enviadas(self):
        for f in (13, 14, 15):
            self._boleta(f)
        with patch('requests.post', return_value=_ok()):
            _correr()
        sin_enviar = BoletaElectronica.objects.filter(enviada_cliente_at__isnull=True)
        self.assertEqual(sin_enviar.count(), 0)

    def test_dos_visitas_distintas_son_dos_mensajes(self):
        # Cada Pase muestra las boletas de SU visita: un solo mensaje dejaría
        # las de la otra sin avisar.
        otra = VentaReserva.objects.create(cliente=self.cliente)
        self._boleta(16)
        self._boleta(17, venta=otra)
        with patch('requests.post', return_value=_ok()) as post:
            _correr()
        self.assertEqual(post.call_count, 2)

    def test_manda_el_nombre_y_el_enlace_del_pase(self):
        self._boleta(18)
        with patch('requests.post', return_value=_ok()) as post:
            _correr()
        enviado = post.call_args.kwargs['json']
        self.assertEqual(enviado['template_name'], 'boleta_electronica')
        self.assertEqual(enviado['texts'][0], 'Marta')          # solo el nombre
        self.assertIn('/ventas/reserva/', enviado['texts'][1])  # el Pase


class AQuienNoSeLeManda(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Iván', telefono='+56987654321')
        self.venta = VentaReserva.objects.create(cliente=self.cliente)

    def _boleta(self, **kw):
        datos = dict(pago=None, venta_reserva=self.venta, ambiente='produccion',
                     folio=20, estado='aceptada', monto_total=10000,
                     monto_neto=8403, monto_iva=1597, emitida_at=timezone.now())
        datos.update(kw)
        return BoletaElectronica.objects.create(**datos)

    def test_a_quien_ya_se_le_envio(self):
        self._boleta(enviada_cliente_at=timezone.now())
        with patch('requests.post') as post:
            _correr()
        self.assertEqual(post.call_count, 0)

    def test_con_la_ventana_abierta_se_deja_para_el_envio_gratis(self):
        # Si el cliente escribió, la fase 2 se la manda con PDF y sin costo.
        self._boleta()
        WhatsAppMessage.objects.create(phone=self.cliente.telefono, direction='in',
                                       msg_type='text', timestamp=timezone.now())
        with patch('requests.post') as post:
            salida = _correr()
        self.assertEqual(post.call_count, 0)
        self.assertIn('ventana abierta', salida)

    def test_sin_telefono(self):
        self.cliente.telefono = ''
        self.cliente.save()
        self._boleta()
        with patch('requests.post') as post:
            _correr()
        self.assertEqual(post.call_count, 0)

    def test_boletas_que_no_son_de_produccion(self):
        self._boleta(ambiente='certificacion')
        with patch('requests.post') as post:
            _correr()
        self.assertEqual(post.call_count, 0)

    def test_boletas_en_error(self):
        self._boleta(estado='error')
        with patch('requests.post') as post:
            _correr()
        self.assertEqual(post.call_count, 0)

    def test_boletas_viejas_fuera_de_la_ventana_de_dias(self):
        self._boleta(emitida_at=timezone.now() - datetime.timedelta(days=30))
        with patch('requests.post') as post:
            _correr(dias=7)
        self.assertEqual(post.call_count, 0)


class SiFallaNoSePierde(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Rosa', telefono='+56911119999')
        self.venta = VentaReserva.objects.create(cliente=self.cliente)
        self.boleta = BoletaElectronica.objects.create(
            pago=None, venta_reserva=self.venta, ambiente='produccion',
            folio=30, estado='aceptada', monto_total=10000, monto_neto=8403,
            monto_iva=1597, emitida_at=timezone.now())

    def test_si_el_backend_falla_NO_la_marca_como_enviada(self):
        # Marcarla dejaría al cliente sin su boleta y sin que nadie lo note.
        malo = MagicMock(); malo.status_code = 502; malo.text = 'caído'
        with patch('requests.post', return_value=malo):
            _correr()
        self.boleta.refresh_from_db()
        self.assertIsNone(self.boleta.enviada_cliente_at)

    def test_un_error_de_red_no_tumba_la_corrida(self):
        with patch('requests.post', side_effect=RuntimeError('sin red')):
            salida = _correr()   # no debe lanzar
        self.assertIn('fallidos: 1', salida)

    def test_simular_no_manda_ni_marca(self):
        with patch('requests.post') as post:
            salida = _correr(simular=True)
        self.assertEqual(post.call_count, 0)
        self.assertIn('[simulado]', salida)
        self.boleta.refresh_from_db()
        self.assertIsNone(self.boleta.enviada_cliente_at)
