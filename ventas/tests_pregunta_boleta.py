"""La pregunta «¿Desea generar la boleta electrónica?» al cobrar en la tarjeta.

Diseño de Jorge (02-09-2026), y el porqué de cada regla:

· NO automático. Muchas ventas ya las informa el recaudador (Flow, los links de
  Mercado Pago, el voucher de SumUp). Emitir automáticamente boletearía dos
  veces la misma venta, y un duplicado ante el SII cuesta más de arreglar que
  una boleta que falta.
· La pregunta aparece SOLO en los medios que sí boletean — efectivo y
  transferencias. Con tarjeta el voucher ya es la boleta.
· El «no» se guarda con nombre y hora. Un pago sin boleta y sin decisión es
  indistinguible de un olvido; el listado aparte existe para separarlos.
· El pago se guarda ANTES de tocar el SII. Si la emisión falla, la plata
  registrada no se pierde: eso dejaría a Deborah sin poder cobrar.

Ejecutar:
    python manage.py test ventas.tests_pregunta_boleta
"""
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from facturacion.models import (BoletaElectronica, ConfiguracionFacturacion,
                                DecisionSinBoleta, MedioPago)
from ventas.models import Cliente, Pago, VentaReserva


class BaseTarjeta(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='cajera_boleta', email='s@test.cl', password='x')
        cls.cliente = Cliente.objects.create(nombre='Nora', telefono='+56922222222')
        cls.venta = VentaReserva.objects.create(cliente=cls.cliente)

        # El mapa real reducido: dos que boletean, dos que no.
        MedioPago.objects.create(codigo='efectivo', nombre='Efectivo',
                                 genera_boleta=True, visible_al_cobrar=True)
        MedioPago.objects.create(codigo='mercadopagoaremko',
                                 nombre='Transferencia a Mercado Pago',
                                 genera_boleta=True, visible_al_cobrar=True)
        MedioPago.objects.create(codigo='tarjeta', nombre='Tarjeta (SumUp)',
                                 genera_boleta=False, visible_al_cobrar=True)
        MedioPago.objects.create(codigo='flow', nombre='Flow (web)',
                                 genera_boleta=False, visible_al_cobrar=False)

    def setUp(self):
        self.client.force_login(self.staff)

    def _cobrar(self, monto=10000, metodo='efectivo', **extra):
        datos = {'monto': str(monto), 'metodo_pago': metodo}
        datos.update(extra)
        return self.client.post(
            reverse('ventas:tarjeta_agregar_pago', args=[self.venta.pk]), datos)


class LaPreguntaAparecleDondeCorresponde(BaseTarjeta):
    def _codigos(self):
        r = self.client.get(reverse('ventas:tarjeta_reserva', args=[self.venta.pk]))
        return json.loads(r.context['medios_que_boletean'])

    def test_efectivo_y_transferencia_preguntan(self):
        codigos = self._codigos()
        self.assertIn('efectivo', codigos)
        self.assertIn('mercadopagoaremko', codigos)

    def test_la_tarjeta_no_pregunta(self):
        # El voucher de SumUp YA es la boleta: preguntar acá invita a duplicar.
        self.assertNotIn('tarjeta', self._codigos())

    def test_flow_no_pregunta(self):
        self.assertNotIn('flow', self._codigos())

    def test_la_pregunta_esta_en_la_pagina(self):
        r = self.client.get(reverse('ventas:tarjeta_reserva', args=[self.venta.pk]))
        html = r.content.decode()
        self.assertIn('¿Desea generar la boleta electrónica?', html)
        self.assertIn('name="emitir_boleta" value="si"', html)
        self.assertIn('name="emitir_boleta" value="no"', html)

    def test_el_javascript_recibe_una_lista_de_verdad(self):
        # |safe imprime el JSON crudo dentro del script: si dejara de ser una
        # lista válida, la página entera se rompe en silencio.
        r = self.client.get(reverse('ventas:tarjeta_reserva', args=[self.venta.pk]))
        crudo = r.content.decode().split('var BOLETEAN = ')[1].split(';')[0]
        self.assertIsInstance(json.loads(crudo), list)


class ElNoQuedaRegistrado(BaseTarjeta):
    def test_guarda_quien_decidio_no_emitir(self):
        r = self._cobrar(emitir_boleta='no')
        self.assertEqual(r.status_code, 200)
        decision = DecisionSinBoleta.objects.get()
        self.assertEqual(decision.usuario, self.staff)
        self.assertEqual(decision.pago.monto, 10000)

    def test_no_emite_boleta(self):
        self._cobrar(emitir_boleta='no')
        self.assertFalse(BoletaElectronica.objects.exists())

    def test_el_pago_se_guarda_igual(self):
        self._cobrar(emitir_boleta='no')
        self.assertEqual(Pago.objects.count(), 1)

    def test_avisa_en_pantalla(self):
        r = self._cobrar(emitir_boleta='no')
        self.assertIn('revisión', r.json()['boleta'])


class ElSiEmite(BaseTarjeta):
    def test_llama_al_emisor(self):
        with patch('facturacion.services.emisor.emitir_boleta_para_pago') as emisor:
            emisor.return_value = (None, 'probando')
            self._cobrar(emitir_boleta='si')
            self.assertEqual(emisor.call_count, 1)

    def test_no_registra_decision_de_no_emitir(self):
        with patch('facturacion.services.emisor.emitir_boleta_para_pago') as emisor:
            emisor.return_value = (None, 'probando')
            self._cobrar(emitir_boleta='si')
        self.assertFalse(DecisionSinBoleta.objects.exists())

    def test_si_el_sii_falla_el_pago_no_se_pierde(self):
        # La plata cobrada es un hecho; la boleta es un trámite. Si se cae el
        # SII, se avisa — pero el pago queda.
        with patch('facturacion.services.emisor.emitir_boleta_para_pago',
                   side_effect=RuntimeError('SII caído')):
            r = self._cobrar(emitir_boleta='si')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Pago.objects.count(), 1)
        self.assertIn('falló', r.json()['boleta'])


class SinRespuestaNoSeInventaNada(BaseTarjeta):
    def test_un_cobro_con_tarjeta_no_deja_decision(self):
        self._cobrar(metodo='tarjeta')
        self.assertFalse(DecisionSinBoleta.objects.exists())
        self.assertFalse(BoletaElectronica.objects.exists())

    def test_sin_el_campo_no_se_asume_que_no(self):
        # Que falte la respuesta no es un «no»: un «no» tiene autor y hora.
        self._cobrar(metodo='efectivo')
        self.assertFalse(DecisionSinBoleta.objects.exists())


class ElListadoAparte(BaseTarjeta):
    """/boletas/pendientes/ — la otra mitad del diseño."""

    def _ver(self):
        return self.client.get(reverse('facturacion:pagos_sin_boleta'))

    def test_el_no_decidido_sale_como_alerta(self):
        self._cobrar(monto=45000, metodo='efectivo')
        r = self._ver()
        self.assertEqual(len(r.context['sin_decidir']), 1)
        self.assertEqual(r.context['total_sin_decidir'], 45000)

    def test_el_decidido_va_al_otro_grupo(self):
        self._cobrar(monto=45000, emitir_boleta='no')
        r = self._ver()
        self.assertEqual(len(r.context['sin_decidir']), 0)
        self.assertEqual(len(r.context['con_decision']), 1)

    def test_los_medios_que_no_boletean_no_aparecen(self):
        self._cobrar(metodo='tarjeta')
        r = self._ver()
        self.assertEqual(len(r.context['sin_decidir']), 0)
        self.assertEqual(len(r.context['con_decision']), 0)

    def test_lo_ya_boleteado_desaparece_del_listado(self):
        self._cobrar(metodo='efectivo')
        ConfiguracionFacturacion.get()
        BoletaElectronica.objects.create(
            pago=Pago.objects.get(), venta_reserva=self.venta, folio=91,
            estado='aceptada', monto_total=10000, monto_neto=8403, monto_iva=1597)
        self.assertEqual(len(self._ver().context['sin_decidir']), 0)

    def test_una_boleta_con_error_no_lo_tapa(self):
        # Una boleta en estado error NO es una boleta: el pago sigue pendiente.
        self._cobrar(metodo='efectivo')
        BoletaElectronica.objects.create(
            pago=Pago.objects.get(), venta_reserva=self.venta,
            estado='error', monto_total=10000, monto_neto=8403, monto_iva=1597)
        self.assertEqual(len(self._ver().context['sin_decidir']), 1)

    def test_una_devolucion_no_es_un_pendiente(self):
        # Una devolución no se boletea: se anula con nota de crédito, y esas
        # se emiten en el sistema del SII (decisión de Jorge, 02-09-2026).
        # Si apareciera acá sería un pendiente que nadie puede resolver nunca.
        Pago.objects.create(venta_reserva=self.venta, monto=-45000,
                            metodo_pago='efectivo', usuario=self.staff)
        r = self._ver()
        self.assertEqual(len(r.context['sin_decidir']), 0)
        self.assertEqual(len(r.context['con_decision']), 0)

    def test_la_pagina_dice_cuantas_devoluciones_dejo_fuera(self):
        # Un total que no declara lo que excluye, miente.
        Pago.objects.create(venta_reserva=self.venta, monto=-45000,
                            metodo_pago='efectivo', usuario=self.staff)
        r = self._ver()
        self.assertEqual(r.context['devoluciones'], 1)
        self.assertIn('nota de crédito', r.content.decode())

    def test_una_devolucion_no_suma_al_total(self):
        self._cobrar(monto=50000, metodo='efectivo')
        Pago.objects.create(venta_reserva=self.venta, monto=-45000,
                            metodo_pago='efectivo', usuario=self.staff)
        self.assertEqual(self._ver().context['total_sin_decidir'], 50000)

    def test_se_llega_desde_el_panel(self):
        # Un listado de control al que nadie llega no controla nada.
        html = self.client.get('/admin/').content.decode()
        self.assertIn(reverse('facturacion:pagos_sin_boleta'), html)

    def test_la_pagina_es_solo_para_staff(self):
        self.client.logout()
        r = self._ver()
        self.assertIn(r.status_code, (302, 403))


class LaBoletaSeVeEnLaTarjeta(BaseTarjeta):
    """Jorge, mirando la tarjeta de la reserva 6741 (04-09-2026): «en la
    primera boleta creada, ¿debería aparecer la boleta o el link acá?».

    Sí. El plan decía que cada pago mostraría su folio en la tarjeta, pero eso
    solo se había hecho en el Pase del cliente. Sin esto, Deborah cobra, se
    emite la boleta, y en la misma pantalla no queda rastro de que exista.
    """

    def _tarjeta(self):
        return self.client.get(reverse('ventas:tarjeta_reserva', args=[self.venta.pk]))

    def _pago_con_boleta(self, folio=69012):
        from facturacion.models import BoletaElectronica
        self._cobrar(monto=500, metodo='efectivo')
        pago = Pago.objects.latest('id')
        return BoletaElectronica.objects.create(
            pago=pago, venta_reserva=self.venta, ambiente='produccion',
            folio=folio, estado='aceptada', monto_total=500,
            monto_neto=420, monto_iva=80)

    def test_muestra_el_folio_de_la_boleta(self):
        self._pago_con_boleta()
        self.assertIn('Boleta 69012', self._tarjeta().content.decode())

    def test_el_folio_es_un_enlace_a_la_boleta(self):
        b = self._pago_con_boleta()
        self.assertIn(f'/boletas/b/{b.token_consulta}/',
                      self._tarjeta().content.decode())

    def test_un_pago_sin_resolver_ofrece_decidir(self):
        # Antes esto solo se veía en el listado aparte, que es un repaso
        # posterior: acá está donde se cobra.
        self._cobrar(monto=40000, metodo='efectivo')
        html = self._tarjeta().content.decode()
        self.assertIn('Falta decidir la boleta', html)
        self.assertIn('/boletas/decidir/', html)

    def test_un_pago_que_no_boletea_no_muestra_nada(self):
        self._cobrar(monto=40000, metodo='tarjeta')
        html = self._tarjeta().content.decode()
        self.assertNotIn('Falta decidir la boleta', html)
        self.assertNotIn('🧾 Boleta', html)

    def test_una_boleta_en_error_no_se_muestra_como_emitida(self):
        from facturacion.models import BoletaElectronica
        self._cobrar(monto=500, metodo='efectivo')
        BoletaElectronica.objects.create(
            pago=Pago.objects.latest('id'), venta_reserva=self.venta,
            ambiente='produccion', folio=99, estado='error',
            monto_total=500, monto_neto=420, monto_iva=80)
        html = self._tarjeta().content.decode()
        self.assertNotIn('Boleta 99', html)

    def test_un_problema_con_las_boletas_no_tumba_la_tarjeta(self):
        from unittest.mock import patch
        self._cobrar(monto=500, metodo='efectivo')
        with patch('facturacion.services.decision.pagos_sin_resolver',
                   side_effect=RuntimeError('BD caída')):
            r = self._tarjeta()
        self.assertEqual(r.status_code, 200)
