"""Los dos huecos de la Declaración de Cumplimiento del SII: generar el RCOF
diario (punto 4) y cuadrar los envíos aceptados/rechazados/con reparos
(punto 7).

Revisando el formulario del SII con Jorge (03-09-2026) encontramos que 3 de
los 9 requisitos declarados no eran ciertos todavía. Dos se resuelven acá:

· Punto 4 — «Envío diario del RCOF». El SII rechaza este documento por API
  desde 2022 (ya no es obligatorio, y su propio backend lo dice: "Impuestos
  Internos ya no admite este tipo de documento"). Por eso `generar_rcof_diario`
  NO envía nada: genera, firma y valida, y esa validación diaria persistida
  ES la evidencia de capacidad — no un envío que el SII mismo bloquea.

· Punto 7 — «Cuadratura de envíos aceptados, rechazados y con reparos».
  `cuadrar_envios_sii` consulta el resultado real de cada trackId y
  reclasifica cada boleta. El formato de respuesta usado en las pruebas está
  tomado de un envío real (trackId 32124491, 03-09-2026), no inventado.

Ejecutar:
    python manage.py test facturacion.tests_declaracion_cumplimiento
"""
from __future__ import annotations

from unittest.mock import patch
from io import StringIO

from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError

from facturacion.models import BoletaElectronica, ReporteConsumoFolios
from facturacion.management.commands.generar_rcof_diario import Command as RcofCommand


def _boleta(ambiente='certificacion', estado='enviada', folio=1, track_id='',
           fecha_emis='2026-09-01'):
    return BoletaElectronica.objects.create(
        pago=None, tipo_dte=39, ambiente=ambiente, folio=folio, track_id=track_id,
        monto_total=10000, monto_neto=8403, monto_iva=1597, glosa='prueba',
        estado=estado, xml_dte=f'<DTE><FchEmis>{fecha_emis}</FchEmis></DTE>')


def _run_rcof(**opts):
    out = StringIO()
    call_command('generar_rcof_diario', stdout=out, **opts)
    return out.getvalue()


def _run_cuadrar(**opts):
    out = StringIO()
    call_command('cuadrar_envios_sii', stdout=out, **opts)
    return out.getvalue()


CREDS_OK = patch('facturacion.services.simpleapi_client.credenciales_listas',
                 return_value=True)
CERT_OK = patch('facturacion.services.simpleapi_client.obtener_certificado',
                return_value=(b'cert', 'clave'))
RCOF_OK = patch('facturacion.services.rcof_builder.construir_consumo_folios',
                return_value=('<ConsumoFolios>x</ConsumoFolios>', 'DOC1'))
FIRMAR_OK = patch('facturacion.services.rcof_builder.firmar',
                  return_value='<ConsumoFolios firmado="si">x</ConsumoFolios>')
VALIDA_OK = patch.object(RcofCommand, '_validar_contra_xsd', return_value=(True, ''))


class GenerarRcofDiario(TestCase):
    @CREDS_OK
    @CERT_OK
    @RCOF_OK
    @FIRMAR_OK
    @VALIDA_OK
    def test_genera_y_persiste_un_reporte_valido(self, _v, _f, _r, _c, _cr):
        _boleta(ambiente='certificacion', fecha_emis='2026-09-01')
        _run_rcof(fecha='2026-09-01', ambiente='certificacion')
        r = ReporteConsumoFolios.objects.get()
        self.assertTrue(r.valido)
        self.assertEqual(r.cantidad_folios, 1)

    @CREDS_OK
    @patch('facturacion.services.simpleapi_client.obtener_certificado')
    @RCOF_OK
    @FIRMAR_OK
    def test_no_lo_marca_valido_si_la_validacion_falla(self, _r, _f, cert, _creds):
        cert.return_value = (b'cert', 'clave')
        _boleta(ambiente='certificacion', fecha_emis='2026-09-01')
        with patch.object(RcofCommand, '_validar_contra_xsd',
                          return_value=(False, 'línea 5: elemento inesperado')):
            with self.assertRaises(CommandError):
                _run_rcof(fecha='2026-09-01', ambiente='certificacion')
        r = ReporteConsumoFolios.objects.get()
        # Se persiste igual -- CON el error -- para que quede evidencia de
        # que se intentó y de qué falló, no un silencio.
        self.assertFalse(r.valido)
        self.assertIn('elemento inesperado', r.error_validacion)

    @CREDS_OK
    @CERT_OK
    @RCOF_OK
    @FIRMAR_OK
    @VALIDA_OK
    def test_no_regenera_si_ya_hay_uno_valido(self, _v, _f, _r, _c, _cr):
        _boleta(ambiente='certificacion', fecha_emis='2026-09-01')
        _run_rcof(fecha='2026-09-01', ambiente='certificacion')
        with patch('facturacion.services.rcof_builder.construir_consumo_folios') as m:
            _run_rcof(fecha='2026-09-01', ambiente='certificacion')
            self.assertEqual(m.call_count, 0)

    @CREDS_OK
    @CERT_OK
    @RCOF_OK
    @FIRMAR_OK
    @VALIDA_OK
    def test_forzar_si_regenera(self, _v, _f, _r, _c, _cr):
        _boleta(ambiente='certificacion', fecha_emis='2026-09-01')
        _run_rcof(fecha='2026-09-01', ambiente='certificacion')
        with patch('facturacion.services.rcof_builder.construir_consumo_folios',
                   return_value=('<ConsumoFolios>x</ConsumoFolios>', 'DOC1')) as m:
            _run_rcof(fecha='2026-09-01', ambiente='certificacion', forzar=True)
            self.assertEqual(m.call_count, 1)

    @CREDS_OK
    @CERT_OK
    def test_sin_boletas_del_dia_no_es_un_error(self, _c, _creds):
        # Un día de cierre (0 boletas) es un resultado válido, no una falla.
        _run_rcof(fecha='2026-09-01', ambiente='certificacion')
        self.assertFalse(ReporteConsumoFolios.objects.exists())

    def test_ambiente_simulado_no_genera_nada(self):
        with patch('facturacion.services.simpleapi_client.credenciales_listas') as creds:
            _run_rcof(fecha='2026-09-01')  # sin --ambiente: usa config (simulado)
            self.assertEqual(creds.call_count, 0)

    @CREDS_OK
    @CERT_OK
    @RCOF_OK
    @FIRMAR_OK
    @VALIDA_OK
    def test_no_mezcla_boletas_de_otra_fecha(self, _v, _f, _r, _c, _cr):
        _boleta(ambiente='certificacion', folio=1, fecha_emis='2026-09-01')
        _boleta(ambiente='certificacion', folio=2, fecha_emis='2026-08-15')
        _run_rcof(fecha='2026-09-01', ambiente='certificacion')
        r = ReporteConsumoFolios.objects.get()
        self.assertEqual(r.cantidad_folios, 1)

    @CREDS_OK
    @CERT_OK
    @RCOF_OK
    @FIRMAR_OK
    @VALIDA_OK
    def test_no_incluye_boletas_en_error(self, _v, _f, _r, _c, _cr):
        _boleta(ambiente='certificacion', estado='error', fecha_emis='2026-09-01')
        _run_rcof(fecha='2026-09-01', ambiente='certificacion')
        self.assertFalse(ReporteConsumoFolios.objects.exists())


RESPUESTA_REAL_EPR = {
    'estado': 'EPR',
    'estadistica': [{'tipo': 39, 'informados': 3, 'aceptados': 1,
                     'rechazados': 0, 'reparos': 2}],
    'detalles': [
        {'folio': 6, 'estado': 'RLV', 'descripcion': 'DTE Aceptado con Reparos Leves',
         'errores': [{'codigo': 650, 'descripcion': 'Documento excede plazo'}]},
        {'folio': 7, 'estado': 'RLV', 'descripcion': 'DTE Aceptado con Reparos Leves',
         'errores': [{'codigo': 650, 'descripcion': 'Documento excede plazo'}]},
    ],
}


class CuadrarEnviosSii(TestCase):
    @CREDS_OK
    @CERT_OK
    @patch('facturacion.services.simpleapi_client.consultar_estado_envio')
    def test_clasifica_aceptada_limpia_y_con_reparo(self, consultar, _c, _creds):
        consultar.return_value = RESPUESTA_REAL_EPR
        limpia = _boleta(ambiente='certificacion', folio=8, track_id='999')
        con_reparo = _boleta(ambiente='certificacion', folio=6, track_id='999')
        _run_cuadrar(ambiente='certificacion')
        limpia.refresh_from_db()
        con_reparo.refresh_from_db()
        self.assertEqual(limpia.estado, 'aceptada')
        self.assertEqual(limpia.error_mensaje, '')
        self.assertEqual(con_reparo.estado, 'aceptada')
        self.assertIn('reparo', con_reparo.error_mensaje.lower())

    @CREDS_OK
    @CERT_OK
    @patch('facturacion.services.simpleapi_client.consultar_estado_envio')
    def test_clasifica_rechazada(self, consultar, _c, _creds):
        consultar.return_value = {
            'estado': 'EPR',
            'estadistica': [{'tipo': 39, 'informados': 1, 'aceptados': 0,
                             'rechazados': 1, 'reparos': 0}],
            'detalles': [{'folio': 6, 'estado': 'RCH',
                         'descripcion': 'DTE Rechazado por Firma Invalida'}],
        }
        b = _boleta(ambiente='certificacion', folio=6, track_id='999')
        _run_cuadrar(ambiente='certificacion')
        b.refresh_from_db()
        self.assertEqual(b.estado, 'rechazada')

    @CREDS_OK
    @CERT_OK
    @patch('facturacion.services.simpleapi_client.consultar_estado_envio')
    def test_sobre_completo_rechazado_vuelve_a_generada_para_reintentar(
            self, consultar, _c, _creds):
        consultar.return_value = {'estado': 'RECHAZADO'}
        b = _boleta(ambiente='certificacion', folio=6, track_id='999')
        _run_cuadrar(ambiente='certificacion')
        b.refresh_from_db()
        self.assertEqual(b.estado, 'generada')
        self.assertEqual(b.track_id, '')

    @CREDS_OK
    @CERT_OK
    @patch('facturacion.services.simpleapi_client.consultar_estado_envio')
    def test_todavia_procesando_no_se_toca(self, consultar, _c, _creds):
        consultar.return_value = {'estado': 'REC'}
        b = _boleta(ambiente='certificacion', folio=6, track_id='999')
        _run_cuadrar(ambiente='certificacion')
        b.refresh_from_db()
        self.assertEqual(b.estado, 'enviada')

    @CREDS_OK
    @CERT_OK
    @patch('facturacion.services.simpleapi_client.consultar_estado_envio')
    def test_estado_desconocido_no_se_toca(self, consultar, _c, _creds):
        # Ante un valor de estado que no está documentado, no se adivina.
        consultar.return_value = {'estado': 'ALGO-NUEVO-DEL-SII'}
        b = _boleta(ambiente='certificacion', folio=6, track_id='999')
        _run_cuadrar(ambiente='certificacion')
        b.refresh_from_db()
        self.assertEqual(b.estado, 'enviada')

    @CREDS_OK
    @CERT_OK
    @patch('facturacion.services.simpleapi_client.consultar_estado_envio')
    def test_descripcion_sin_palabra_clave_no_se_adivina(self, consultar, _c, _creds):
        consultar.return_value = {
            'estado': 'EPR',
            'estadistica': [{'tipo': 39, 'informados': 1, 'aceptados': 0,
                             'rechazados': 0, 'reparos': 1}],
            'detalles': [{'folio': 6, 'descripcion': 'Observación sin clasificar'}],
        }
        b = _boleta(ambiente='certificacion', folio=6, track_id='999')
        _run_cuadrar(ambiente='certificacion')
        b.refresh_from_db()
        # Ni aceptada ni rechazada: se queda visible, no se inventa un veredicto.
        self.assertEqual(b.estado, 'enviada')
        self.assertIn('sin clasificar', b.error_mensaje.lower())

    @CREDS_OK
    @CERT_OK
    @patch('facturacion.services.simpleapi_client.consultar_estado_envio')
    def test_no_toca_boletas_de_otro_ambiente(self, consultar, _c, _creds):
        consultar.return_value = RESPUESTA_REAL_EPR
        de_prod = _boleta(ambiente='produccion', folio=8, track_id='999')
        _boleta(ambiente='certificacion', folio=8, track_id='999')
        _run_cuadrar(ambiente='certificacion')
        de_prod.refresh_from_db()
        self.assertEqual(de_prod.estado, 'enviada')

    def test_sin_envios_pendientes_no_llama_a_nada(self):
        with patch('facturacion.services.simpleapi_client.credenciales_listas') as creds:
            _run_cuadrar(ambiente='certificacion')
            self.assertEqual(creds.call_count, 0)

    @CREDS_OK
    @CERT_OK
    def test_un_trackid_con_error_no_frena_a_los_demas(self, _c, _creds):
        _boleta(ambiente='certificacion', folio=1, track_id='111111')
        buena = _boleta(ambiente='certificacion', folio=2, track_id='222222')
        with patch('facturacion.services.simpleapi_client.consultar_estado_envio') as m:
            def efecto(track_id, *a, **kw):
                if str(track_id) == '111111':
                    raise Exception('SII caído')
                return {'estado': 'EPR',
                       'estadistica': [{'tipo': 39, 'informados': 1, 'aceptados': 1,
                                       'rechazados': 0, 'reparos': 0}],
                       'detalles': []}
            m.side_effect = efecto
            _run_cuadrar(ambiente='certificacion')
        buena.refresh_from_db()
        self.assertEqual(buena.estado, 'aceptada')
