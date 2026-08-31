"""
Tests de la lógica de emisión (corren con `python manage.py test facturacion`).

Cubren: cálculo neto/IVA, filtro por medio de pago, idempotencia del candado
OneToOne y el modo simulado end-to-end.
"""
import datetime
from django.test import TestCase

from facturacion.models import BoletaElectronica, ConfiguracionFacturacion, MedioPago
from facturacion.services.emisor import (calcular_montos, emitir_boleta_para_pago,
                                         medio_genera_boleta)
from ventas.models import Cliente, Pago, VentaReserva


class CalculoMontosTest(TestCase):
    def test_neto_iva_cuadran_con_el_total(self):
        # $110.000 bruto (cabaña 2 personas): neto 92.437 + IVA 17.563
        neto, iva = calcular_montos(110000)
        self.assertEqual(neto, 92437)
        self.assertEqual(iva, 17563)
        self.assertEqual(neto + iva, 110000)

    def test_montos_chicos(self):
        neto, iva = calcular_montos(1190)
        self.assertEqual(neto, 1000)
        self.assertEqual(iva, 190)


class EmisionTest(TestCase):
    def setUp(self):
        MedioPago.objects.create(codigo='transferencia', nombre='Transferencia', genera_boleta=True)
        MedioPago.objects.create(codigo='mercadopago_link', nombre='Link MP', genera_boleta=False)
        config = ConfiguracionFacturacion.get()
        config.ambiente = 'simulado'
        config.save()
        self.cliente = Cliente.objects.create(nombre='Test Boleta', telefono='+56999999901')
        self.reserva = VentaReserva.objects.create(cliente=self.cliente)

    def _pago(self, metodo='transferencia', monto=50000):
        return Pago.objects.create(venta_reserva=self.reserva, monto=monto, metodo_pago=metodo)

    def test_medio_no_boleteable_no_emite(self):
        pago = self._pago(metodo='mercadopago_link')
        boleta, mensaje = emitir_boleta_para_pago(pago)
        self.assertIsNone(boleta)
        self.assertIn('no genera boleta', mensaje)
        self.assertFalse(medio_genera_boleta('mercadopago_link'))

    def test_emision_simulada(self):
        pago = self._pago()
        boleta, mensaje = emitir_boleta_para_pago(pago)
        self.assertIsNotNone(boleta)
        self.assertEqual(boleta.estado, 'simulada')
        self.assertEqual(int(boleta.monto_total), 50000)
        self.assertEqual(int(boleta.monto_neto) + int(boleta.monto_iva), 50000)
        self.assertIsNotNone(boleta.emitida_at)

    def test_idempotencia_no_duplica(self):
        pago = self._pago()
        b1, _ = emitir_boleta_para_pago(pago)
        b2, mensaje = emitir_boleta_para_pago(pago)
        self.assertEqual(b1.pk, b2.pk)
        self.assertIn('ya existía', mensaje)
        self.assertEqual(BoletaElectronica.objects.filter(pago=pago).count(), 1)

    def test_monto_cero_no_emite(self):
        pago = self._pago(monto=0)
        boleta, mensaje = emitir_boleta_para_pago(pago)
        self.assertIsNone(boleta)
        self.assertIn('monto', mensaje)

    def test_medio_desconocido_no_emite(self):
        pago = self._pago(metodo='flow')  # sin fila MedioPago
        boleta, _ = emitir_boleta_para_pago(pago)
        self.assertIsNone(boleta)


class ConsultaDeEstadoDelEnvio(TestCase):
    """P-16: consultar al SII el estado de un envío por trackId (2026-08-31).

    Cierra el ciclo del set: el sobre quedó REC (trackId 32032105) y esto
    pregunta si el SII lo ACEPTÓ. El endpoint viene del código fuente público
    del SDK oficial (POST /api/v1/consulta/envio, multipart input + .pfx),
    con el mismo contrato multipart del hermano enviar_sobre.
    """

    def _config(self):
        from facturacion.models import ConfiguracionFacturacion

        config = ConfiguracionFacturacion.get()
        config.rut_emisor = '76485192-7'
        config.rut_firmante = '7604892-4'
        config.save()
        return config

    def test_arma_la_consulta_con_el_contrato_del_hermano(self):
        from unittest.mock import patch

        from facturacion.services import simpleapi_client as cli

        config = self._config()
        with patch.object(cli, '_post_multipart',
                          return_value={'estado': 'EPR', 'ok': True}) as pm:
            r = cli.consultar_estado_envio(32032105, b'PFX', 'clave',
                                           config, ambiente_num=0)
        self.assertEqual(r['estado'], 'EPR')
        url, input_json, archivos = pm.call_args.args[:3]
        self.assertTrue(url.endswith('/api/v1/consulta/envio'))
        self.assertEqual(input_json['TrackId'], 32032105)
        self.assertEqual(input_json['RutEmpresa'], '76485192-7')
        self.assertEqual(input_json['Ambiente'], 0)
        self.assertTrue(input_json['ServidorBoletaREST'],
                        'las boletas van al SII REST, no al SOAP de DTE')
        self.assertEqual(input_json['Certificado']['Rut'], '7604892-4')
        # El contrato de _post_multipart: tuplas de 4 y el cert en 'files'.
        self.assertEqual(archivos[0][0], 'files')
        self.assertEqual(len(archivos[0]), 4)

    def test_el_comando_usa_el_trackid_de_las_boletas_del_set(self):
        from unittest.mock import patch

        from django.core.management import call_command

        from facturacion.models import BoletaElectronica

        self._config()
        BoletaElectronica.objects.create(caso_set='CASO-1', folio=1,
                                         track_id='32032105', estado='enviada',
                                         monto_total=19900, monto_neto=16723,
                                         monto_iva=3177)
        with patch('facturacion.services.simpleapi_client.credenciales_listas',
                   return_value=True), \
             patch('facturacion.services.simpleapi_client.obtener_certificado',
                   return_value=(b'PFX', 'clave')), \
             patch('facturacion.services.simpleapi_client.consultar_estado_envio',
                   return_value={'estado': 'ACEPTADO'}) as consulta:
            call_command('consultar_envio')
        self.assertEqual(consulta.call_args.args[0], 32032105)


class LaReferenciaDelSetEsDeBoleta(TestCase):
    """El rechazo LSX-00204 (trackId 32032105): mandamos TipoDocumento=SET y
    SimpleAPI serializó <TpoDocRef> — un campo de FACTURA, ilegal en el
    esquema de boletas. La Referencia de boleta solo admite NroLinRef +
    CodRef + RazonRef, y el instructivo del SII lo ejemplifica textual:
    <CodRef> SET / <RazonRef> CASO-1.

    Guarda de fuente: si alguien vuelve a armar la referencia con ojos de
    factura, esto cae ANTES de quemar folios del CAF."""

    def test_el_set_manda_codref_y_no_tipodocumento(self):
        import os

        from django.conf import settings

        src = open(os.path.join(settings.BASE_DIR, 'facturacion', 'management',
                                'commands', 'ejecutar_set_pruebas.py'),
                   encoding='utf-8').read()
        self.assertIn('"CodigoReferencia": "SET"', src)
        self.assertIn('"TipoDocumento": None', src,
                      'sin el null explícito, SimpleAPI emite <TpoDocRef/> '
                      'vacío y el SII rechaza el sobre completo')
        self.assertIn('"RazonReferencia"', src)
        self.assertNotIn('"TipoDocumento": "SET"', src,
                         'volvió la referencia estilo factura: el SII la '
                         'rechaza entera por schema en boletas')
        self.assertNotIn('"FolioReferencia"', src,
                         'FolioRef tampoco existe en la Referencia de boleta')


class ComparacionDeRutDelCertificado(TestCase):
    """El certificado de e-certchile trae el RUT con cero de relleno
    (07604892-4) y la configuración lo guarda sin él (7604892-4). Comparar
    literalmente acusaba un error de configuración que no existía y mandaba
    el diagnóstico por el camino equivocado."""

    def test_el_cero_de_relleno_no_hace_distintos_dos_ruts_iguales(self):
        from facturacion.management.commands.ver_certificado import _solo_digitos

        self.assertEqual(_solo_digitos('07604892-4'), _solo_digitos('7604892-4'))
        self.assertEqual(_solo_digitos('7.604.892-4'), _solo_digitos('7604892-4'))
        self.assertNotEqual(_solo_digitos('76485192-7'), _solo_digitos('7604892-4'))


class PaginaPublicaDeConsulta(TestCase):
    """La página que el SII exige y revisa antes de autorizar. Es pública: lo
    que muestre se lo está afirmando a un cliente."""

    def setUp(self):
        config = ConfiguracionFacturacion.get()
        config.rut_emisor = '76485192-7'
        config.razon_social = 'AREMKO HOTEL SPA'
        config.save()
        self.real = BoletaElectronica.objects.create(
            tipo_dte=39, ambiente='produccion', folio=1024, estado='aceptada',
            monto_neto=92437, monto_iva=17563, monto_total=110000,
            glosa='Pausa junto al río')
        self.del_set = BoletaElectronica.objects.create(
            tipo_dte=39, ambiente='certificacion', folio=19, estado='enviada',
            monto_neto=25042, monto_iva=4758, monto_total=29800,
            glosa='SET SII CASO-1', caso_set='CASO-1')

    def test_una_boleta_real_se_encuentra_con_folio_y_monto(self):
        r = self.client.get('/boletas/consulta/', {'folio': '1024', 'monto': '110000'})
        self.assertContains(r, 'Boleta encontrada')
        self.assertContains(r, 'Pausa junto al río')
        self.assertContains(r, '76485192-7')  # el emisor, para que el cliente confirme

    def test_la_boleta_de_certificacion_NO_es_publica(self):
        # Es un documento de prueba: mostrarlo como «✔ Boleta encontrada» le
        # miente al cliente, y el SII revisa este enlace.
        r = self.client.get('/boletas/consulta/', {'folio': '19', 'monto': '29800'})
        self.assertNotContains(r, 'Boleta encontrada')
        self.assertNotContains(r, 'CASO-1')
        self.assertContains(r, 'No encontramos')

    def test_el_monto_equivocado_no_abre_la_boleta(self):
        r = self.client.get('/boletas/consulta/', {'folio': '1024', 'monto': '1'})
        self.assertNotContains(r, 'Boleta encontrada')

    def test_el_enlace_directo_del_cliente_funciona(self):
        r = self.client.get(f'/boletas/b/{self.real.token_consulta}/')
        self.assertContains(r, 'Boleta encontrada')
        self.assertContains(r, 'Pausa junto al río')

    def test_el_enlace_directo_de_una_de_prueba_no_muestra_nada(self):
        r = self.client.get(f'/boletas/b/{self.del_set.token_consulta}/')
        self.assertNotContains(r, 'Boleta encontrada')
