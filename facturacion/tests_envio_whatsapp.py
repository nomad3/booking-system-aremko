"""Enviarle la boleta al cliente por WhatsApp, dentro de la ventana de 24h.

Decisión de Jorge (04-09-2026): todos reciben su boleta. Dentro de la ventana
de servicio va el PDF adjunto —gratis e inmediato—; fuera de la ventana la
junta el proceso diario en un solo mensaje con plantilla, que se paga.

La propiedad que más importa: **avisar nunca puede voltear una emisión**. La
boleta ya existe ante el SII antes de que intentemos mandar nada, así que
cualquier problema de WhatsApp se registra y se sigue.

Ejecutar:
    python manage.py test facturacion.tests_envio_whatsapp
"""
from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from facturacion.models import BoletaElectronica
from facturacion.services import envio_whatsapp as ew
from ventas.models import Cliente, VentaReserva, WhatsAppMessage

XML = ('<DTE><Documento><Encabezado><IdDoc><Folio>500</Folio>'
       '<FchEmis>2026-09-04</FchEmis></IdDoc><Emisor>'
       '<RUTEmisor>76485192-7</RUTEmisor><RznSocEmisor>AREMKO</RznSocEmisor>'
       '</Emisor><Totales><MntTotal>10000</MntTotal></Totales></Encabezado>'
       '<TED version="1.0"><DD><RE>1-9</RE></DD><FRMT>x</FRMT></TED>'
       '</Documento></DTE>')


class LaVentanaDe24Horas(TestCase):
    def setUp(self):
        self.tel = '+56911112222'

    def _entrante(self, hace_horas):
        WhatsAppMessage.objects.create(
            phone=self.tel, direction='in', msg_type='text',
            timestamp=timezone.now() - datetime.timedelta(hours=hace_horas))

    def test_abierta_si_escribio_hace_poco(self):
        self._entrante(2)
        self.assertTrue(ew.ventana_abierta(self.tel))

    def test_cerrada_si_escribio_hace_mas_de_24h(self):
        self._entrante(25)
        self.assertFalse(ew.ventana_abierta(self.tel))

    def test_cerrada_si_nunca_escribio(self):
        self.assertFalse(ew.ventana_abierta(self.tel))

    def test_un_saliente_NO_abre_la_ventana(self):
        # Solo el mensaje del cliente abre la ventana de servicio; si un
        # saliente contara, se enviaría fuera de plazo y Meta lo rechaza
        # (131047) mientras el sistema cree que llegó.
        WhatsAppMessage.objects.create(
            phone=self.tel, direction='out', msg_type='text',
            timestamp=timezone.now())
        self.assertFalse(ew.ventana_abierta(self.tel))

    def test_sin_telefono_no_revienta(self):
        self.assertFalse(ew.ventana_abierta(''))
        self.assertFalse(ew.ventana_abierta(None))


class ElEnvioDelPdf(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Ana Pérez',
                                              telefono='+56933334444')
        self.venta = VentaReserva.objects.create(cliente=self.cliente)
        self.boleta = BoletaElectronica.objects.create(
            pago=None, venta_reserva=self.venta, ambiente='produccion',
            folio=500, estado='aceptada', monto_total=10000,
            monto_neto=8403, monto_iva=1597, xml_dte=XML)
        WhatsAppMessage.objects.create(
            phone=self.cliente.telefono, direction='in', msg_type='text',
            timestamp=timezone.now())

    def _ok(self):
        r = MagicMock(); r.status_code = 200; return r

    def test_manda_el_pdf_y_deja_constancia(self):
        with patch('facturacion.views._pdf_boleta_impresa', return_value=(b'%PDF-x', '')), \
             patch('requests.post', return_value=self._ok()) as post:
            enviado, motivo = ew.enviar_pdf_al_cliente(self.boleta)
        self.assertTrue(enviado, motivo)
        self.boleta.refresh_from_db()
        self.assertIsNotNone(self.boleta.enviada_cliente_at)
        # Va al teléfono del cliente y como archivo adjunto.
        self.assertEqual(post.call_args.kwargs['data']['to'], '+56933334444')
        self.assertIn('file', post.call_args.kwargs['files'])

    def test_no_la_manda_dos_veces(self):
        self.boleta.enviada_cliente_at = timezone.now()
        self.boleta.save()
        with patch('requests.post') as post:
            enviado, motivo = ew.enviar_pdf_al_cliente(self.boleta)
        self.assertFalse(enviado)
        self.assertEqual(post.call_count, 0)
        self.assertIn('ya se le había enviado', motivo)

    def test_fuera_de_ventana_no_manda_nada(self):
        WhatsAppMessage.objects.all().update(
            timestamp=timezone.now() - datetime.timedelta(hours=30))
        with patch('requests.post') as post:
            enviado, motivo = ew.enviar_pdf_al_cliente(self.boleta)
        self.assertFalse(enviado)
        self.assertEqual(post.call_count, 0)
        self.assertIn('ventana', motivo)

    def test_sin_telefono_no_manda(self):
        self.cliente.telefono = ''
        self.cliente.save()
        with patch('requests.post') as post:
            enviado, motivo = ew.enviar_pdf_al_cliente(self.boleta)
        self.assertFalse(enviado)
        self.assertEqual(post.call_count, 0)

    def test_una_boleta_que_no_es_de_produccion_no_se_le_manda(self):
        # Una de certificación no tiene valor tributario: mandársela al
        # cliente sería entregarle un documento falso. El PDF se mockea para
        # que la ÚNICA razón posible de no enviar sea esta guarda — sin eso el
        # test pasaba porque fallaba al generar el PDF, no por la regla.
        self.boleta.ambiente = 'certificacion'
        self.boleta.save()
        with patch('facturacion.views._pdf_boleta_impresa', return_value=(b'%PDF-x', '')), \
             patch('requests.post', return_value=self._ok()) as post:
            enviado, motivo = ew.enviar_pdf_al_cliente(self.boleta)
        self.assertFalse(enviado)
        self.assertEqual(post.call_count, 0)
        self.assertIn('producción', motivo)

    def test_si_el_backend_falla_no_marca_como_enviada(self):
        malo = MagicMock(); malo.status_code = 502; malo.text = 'upstream'
        with patch('facturacion.views._pdf_boleta_impresa', return_value=(b'%PDF-x', '')), \
             patch('requests.post', return_value=malo):
            enviado, motivo = ew.enviar_pdf_al_cliente(self.boleta)
        self.assertFalse(enviado)
        self.boleta.refresh_from_db()
        self.assertIsNone(self.boleta.enviada_cliente_at)

    def test_si_todo_explota_devuelve_motivo_y_no_lanza(self):
        with patch('facturacion.views._pdf_boleta_impresa',
                   side_effect=RuntimeError('sin memoria')):
            enviado, motivo = ew.enviar_pdf_al_cliente(self.boleta)
        self.assertFalse(enviado)
        self.assertIn('error', motivo.lower())


class AvisarNoPuedeVoltearLaEmision(TestCase):
    """La boleta ya existe ante el SII antes de intentar avisar."""

    def test_la_tarjeta_devuelve_ok_aunque_el_envio_falle(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse

        from facturacion.models import MedioPago

        MedioPago.objects.create(codigo='efectivo', nombre='Efectivo',
                                 genera_boleta=True, visible_al_cobrar=True)
        staff = get_user_model().objects.create_superuser(
            username='cajera_env', email='e@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Luz', telefono='+56955556666')
        venta = VentaReserva.objects.create(cliente=cliente)
        self.client.force_login(staff)

        boleta = MagicMock()
        boleta.folio = 777
        with patch('facturacion.services.emisor.emitir_boleta_para_pago',
                   return_value=(boleta, 'ok')), \
             patch('facturacion.services.envio_whatsapp.enviar_pdf_al_cliente',
                   side_effect=RuntimeError('WhatsApp caído')):
            r = self.client.post(
                reverse('ventas:tarjeta_agregar_pago', args=[venta.pk]),
                {'monto': '10000', 'metodo_pago': 'efectivo', 'emitir_boleta': 'si'})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])
        self.assertIn('777', r.json()['boleta'])
