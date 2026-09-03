"""El envío diario del sobre al SII (P-16, F2 — la mitad que faltaba).

Timbrar una boleta y transmitirla son dos pasos distintos. Al cobrar se
genera y timbra al toque (con folio real del CAF); pero el SII exige además
el envío del sobre EnvioBOLETA — sin eso la boleta queda timbrada pero
nunca llega al SII. `enviar_boletas_sii` es ese segundo paso, pensado para
correr a diario vía cron.

La propiedad que más importa verificar: si el envío falla, las boletas NO
quedan marcadas 'error'. Siguen 'generada' — con su folio y XML intactos —
para que la corrida de mañana las reintente SIN pedir un folio nuevo. Pasar
a 'error' aquí desperdiciaría el folio ya válido en el próximo intento de
emisión de ese mismo pago.

Ejecutar:
    python manage.py test facturacion.tests_enviar_boletas_sii
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse
from django.core.management import call_command
from django.core.management.base import CommandError
from io import StringIO

from facturacion.models import BoletaElectronica, ConfiguracionFacturacion
from facturacion.services.simpleapi_client import SimpleAPIError


def _boleta(ambiente='certificacion', estado='generada', folio=1, tipo_dte=39,
           xml_dte='<DTE>x</DTE>'):
    return BoletaElectronica.objects.create(
        pago=None, tipo_dte=tipo_dte, ambiente=ambiente, folio=folio,
        monto_total=10000, monto_neto=8403, monto_iva=1597,
        glosa='prueba', estado=estado, xml_dte=xml_dte)


def _run(**opts):
    out = StringIO()
    call_command('enviar_boletas_sii', stdout=out, **opts)
    return out.getvalue()


CREDS_OK = patch('facturacion.services.simpleapi_client.credenciales_listas',
                 return_value=True)
CERT_OK = patch('facturacion.services.simpleapi_client.obtener_certificado',
                return_value=(b'cert', 'clave'))


class SinPendientesNoHaceNada(TestCase):
    @CREDS_OK
    @patch('facturacion.services.simpleapi_client.generar_sobre')
    def test_no_llama_a_simpleapi(self, generar_sobre, _creds):
        out = _run(ambiente='certificacion')
        self.assertEqual(generar_sobre.call_count, 0)
        self.assertIn('Sin boletas pendientes', out)


class AmbienteSimuladoEsSeguroPorDefecto(TestCase):
    def test_no_toca_simpleapi_aunque_haya_pendientes_en_otro_ambiente(self):
        # config.ambiente por defecto es 'simulado'. Sin --ambiente, el
        # comando debe usar ESE valor real, no adivinar ni forzar nada. Una
        # boleta de certificación sentada ahí no debe activar ningún envío.
        _boleta(ambiente='certificacion', estado='generada')
        with patch('facturacion.services.simpleapi_client.credenciales_listas') as creds:
            _run()
            self.assertEqual(creds.call_count, 0)

    def test_no_procesa_una_boleta_que_quedo_en_ambiente_simulado(self):
        # El caso que de verdad prueba la guarda: si alguna boleta quedara
        # con ambiente='simulado' Y estado='generada' (no debería ocurrir
        # por el flujo normal, pero el comando tiene que ser seguro igual),
        # que 'simulado' no sea un ambiente real es lo único que evita
        # tratarla como certificación (ambiente_num 0) por accidente.
        _boleta(ambiente='simulado', estado='generada')
        with patch('facturacion.services.simpleapi_client.credenciales_listas') as creds:
            _run()
            self.assertEqual(creds.call_count, 0)


class EnvioExitoso(TestCase):
    def setUp(self):
        self.b1 = _boleta(ambiente='certificacion', estado='generada', folio=10)
        self.b2 = _boleta(ambiente='certificacion', estado='generada', folio=11)

    @CREDS_OK
    @CERT_OK
    @patch('facturacion.services.simpleapi_client.enviar_sobre')
    @patch('facturacion.services.simpleapi_client.generar_sobre')
    def test_marca_enviada_y_guarda_track_id(self, generar_sobre, enviar_sobre,
                                             _cert, _creds):
        generar_sobre.return_value = '<EnvioBOLETA>...</EnvioBOLETA>'
        enviar_sobre.return_value = {'ok': True, 'trackId': '999', 'estado': 'REC'}
        _run(ambiente='certificacion')
        self.b1.refresh_from_db()
        self.b2.refresh_from_db()
        self.assertEqual(self.b1.estado, 'enviada')
        self.assertEqual(self.b2.estado, 'enviada')
        self.assertEqual(self.b1.track_id, '999')

    @CREDS_OK
    @CERT_OK
    @patch('facturacion.services.simpleapi_client.enviar_sobre')
    @patch('facturacion.services.simpleapi_client.generar_sobre')
    def test_manda_las_dos_boletas_en_un_solo_sobre(self, generar_sobre, enviar_sobre,
                                                     _cert, _creds):
        generar_sobre.return_value = '<EnvioBOLETA>...</EnvioBOLETA>'
        enviar_sobre.return_value = {'ok': True, 'trackId': '999', 'estado': 'REC'}
        _run(ambiente='certificacion')
        xmls_enviados = generar_sobre.call_args[0][0]
        self.assertEqual(len(xmls_enviados), 2)


class Aislamiento(TestCase):
    @CREDS_OK
    @CERT_OK
    @patch('facturacion.services.simpleapi_client.enviar_sobre')
    @patch('facturacion.services.simpleapi_client.generar_sobre')
    def test_no_toca_boletas_de_otro_ambiente(self, generar_sobre, enviar_sobre,
                                              _cert, _creds):
        de_prod = _boleta(ambiente='produccion', estado='generada')
        _boleta(ambiente='certificacion', estado='generada')
        generar_sobre.return_value = '<EnvioBOLETA>...</EnvioBOLETA>'
        enviar_sobre.return_value = {'ok': True, 'trackId': '1', 'estado': 'REC'}
        _run(ambiente='certificacion')
        de_prod.refresh_from_db()
        self.assertEqual(de_prod.estado, 'generada')

    @CREDS_OK
    @patch('facturacion.services.simpleapi_client.generar_sobre')
    def test_no_reenvia_estados_ya_resueltos(self, generar_sobre, _creds):
        for estado in ('enviada', 'error', 'simulada', 'pendiente', 'aceptada'):
            _boleta(ambiente='certificacion', estado=estado, folio=None)
        _run(ambiente='certificacion')
        self.assertEqual(generar_sobre.call_count, 0)

    @CREDS_OK
    @CERT_OK
    @patch('facturacion.services.simpleapi_client.enviar_sobre')
    @patch('facturacion.services.simpleapi_client.generar_sobre')
    def test_no_incluye_otro_tipo_de_dte(self, generar_sobre, enviar_sobre,
                                         _cert, _creds):
        _boleta(ambiente='certificacion', estado='generada', tipo_dte=41)
        generar_sobre.return_value = '<EnvioBOLETA>...</EnvioBOLETA>'
        enviar_sobre.return_value = {'ok': True, 'trackId': '1', 'estado': 'REC'}
        _run(ambiente='certificacion')
        self.assertEqual(generar_sobre.call_count, 0)


class SiFallaNoSePierdeElFolio(TestCase):
    """La propiedad central de este comando: un fallo de transmisión jamás
    debe dejar una boleta lista-para-emitir-de-nuevo. El folio ya es válido;
    perder eso de vista es lo que produciría un folio saltado."""

    @CREDS_OK
    @CERT_OK
    @patch('facturacion.services.simpleapi_client.enviar_sobre')
    @patch('facturacion.services.simpleapi_client.generar_sobre')
    def test_si_el_sii_rechaza_el_sobre_la_boleta_sigue_generada(
            self, generar_sobre, enviar_sobre, _cert, _creds):
        b = _boleta(ambiente='certificacion', estado='generada')
        generar_sobre.return_value = '<EnvioBOLETA>...</EnvioBOLETA>'
        enviar_sobre.return_value = {'ok': False, 'estado': 'RCH', 'glosa': 'malo'}
        with self.assertRaises(CommandError):
            _run(ambiente='certificacion')
        b.refresh_from_db()
        self.assertEqual(b.estado, 'generada')
        self.assertEqual(b.track_id, '')

    @CREDS_OK
    @CERT_OK
    @patch('facturacion.services.simpleapi_client.enviar_sobre')
    @patch('facturacion.services.simpleapi_client.generar_sobre')
    def test_si_enviar_sobre_explota_la_boleta_sigue_generada(
            self, generar_sobre, enviar_sobre, _cert, _creds):
        b = _boleta(ambiente='certificacion', estado='generada')
        generar_sobre.return_value = '<EnvioBOLETA>...</EnvioBOLETA>'
        enviar_sobre.side_effect = SimpleAPIError('SII caído')
        with self.assertRaises(CommandError):
            _run(ambiente='certificacion')
        b.refresh_from_db()
        self.assertEqual(b.estado, 'generada')

    @CREDS_OK
    @CERT_OK
    @patch('facturacion.services.simpleapi_client.generar_sobre')
    def test_si_armar_el_sobre_explota_la_boleta_sigue_generada(
            self, generar_sobre, _cert, _creds):
        b = _boleta(ambiente='certificacion', estado='generada')
        generar_sobre.side_effect = SimpleAPIError('formato inválido')
        with self.assertRaises(CommandError):
            _run(ambiente='certificacion')
        b.refresh_from_db()
        self.assertEqual(b.estado, 'generada')

    def test_sin_credenciales_no_avanza(self):
        b = _boleta(ambiente='certificacion', estado='generada')
        with patch('facturacion.services.simpleapi_client.credenciales_listas',
                   return_value=False):
            with self.assertRaises(CommandError):
                _run(ambiente='certificacion')
        b.refresh_from_db()
        self.assertEqual(b.estado, 'generada')


class ElEndpointDelCron(TestCase):
    def setUp(self):
        self.client = Client()

    def test_sin_pendientes_devuelve_ok(self):
        r = self.client.get(reverse('ventas:cron_enviar_boletas_sii'))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])

    def test_token_invalido_devuelve_403(self):
        with patch.dict('os.environ', {'CRON_TOKEN': 'secreto123'}):
            r = self.client.get(reverse('ventas:cron_enviar_boletas_sii'),
                                {'token': 'malo'})
            self.assertEqual(r.status_code, 403)

    def test_token_correcto_pasa(self):
        with patch.dict('os.environ', {'CRON_TOKEN': 'secreto123'}):
            r = self.client.get(reverse('ventas:cron_enviar_boletas_sii'),
                                {'token': 'secreto123'})
            self.assertEqual(r.status_code, 200)

    def test_un_fallo_del_comando_devuelve_500_sin_romper_la_boleta(self):
        b = _boleta(ambiente='certificacion', estado='generada')
        config = ConfiguracionFacturacion.get()
        config.ambiente = 'certificacion'
        config.save()
        with patch('facturacion.services.simpleapi_client.credenciales_listas',
                   return_value=False):
            r = self.client.get(reverse('ventas:cron_enviar_boletas_sii'))
        self.assertEqual(r.status_code, 500)
        self.assertFalse(r.json()['ok'])
        b.refresh_from_db()
        self.assertEqual(b.estado, 'generada')
