"""Cobrar desde el admin también resuelve la boleta.

Deborah lo reportó el 04-09-2026: registró un pago con «Transferencia a
Mercado Pago» en el formulario grande del admin y no le pidió decidir sobre
la boleta. Cierto — la pregunta vivía solo en la tarjeta móvil, así que un
cobro hecho por el admin quedaba sin boleta y se descubría recién al revisar
el listado de pendientes, que es un repaso posterior y no parte del cobro.

El admin guarda varios pagos a la vez, así que no tiene dónde preguntar por
cada uno. La solución es un aviso al guardar, con enlace a la misma decisión
en su propia página.

Ejecutar:
    python manage.py test facturacion.tests_decision_admin
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from facturacion.models import (BoletaElectronica, DecisionSinBoleta, MedioPago)
from facturacion.services.decision import pagos_sin_resolver
from ventas.models import Cliente, Pago, VentaReserva


class QuePagosFaltaResolver(TestCase):
    @classmethod
    def setUpTestData(cls):
        MedioPago.objects.create(codigo='efectivo', nombre='Efectivo',
                                 genera_boleta=True, visible_al_cobrar=True)
        MedioPago.objects.create(codigo='tarjeta', nombre='Tarjeta',
                                 genera_boleta=False, visible_al_cobrar=True)
        cls.cliente = Cliente.objects.create(nombre='Sofía', telefono='+56966666666')
        # Pago.usuario se llena solo con el usuario "actual"; sin uno propio,
        # esta clase hereda el id de otra ya deshecha y sqlite reclama la FK.
        cls.usuario = get_user_model().objects.create_user(
            username='cobra_sofia', password='x')

    def setUp(self):
        self.venta = VentaReserva.objects.create(cliente=self.cliente)

    def _pago(self, monto=10000, metodo='efectivo'):
        return Pago.objects.create(venta_reserva=self.venta, monto=monto,
                                   metodo_pago=metodo, usuario=self.usuario)

    def test_un_pago_que_boletea_y_nadie_miro_aparece(self):
        p = self._pago()
        self.assertEqual([x.pk for x in pagos_sin_resolver(self.venta)], [p.pk])

    def test_uno_que_no_boletea_no_aparece(self):
        self._pago(metodo='tarjeta')
        self.assertEqual(pagos_sin_resolver(self.venta), [])

    def test_uno_ya_boleteado_no_aparece(self):
        p = self._pago()
        BoletaElectronica.objects.create(pago=p, venta_reserva=self.venta, folio=1,
                                         estado='aceptada', monto_total=10000,
                                         monto_neto=8403, monto_iva=1597)
        self.assertEqual(pagos_sin_resolver(self.venta), [])

    def test_una_boleta_en_error_NO_cuenta_como_resuelto(self):
        # Esa boleta no existe ante el SII: el pago sigue pendiente.
        p = self._pago()
        BoletaElectronica.objects.create(pago=p, venta_reserva=self.venta,
                                         estado='error', monto_total=10000,
                                         monto_neto=8403, monto_iva=1597)
        self.assertEqual([x.pk for x in pagos_sin_resolver(self.venta)], [p.pk])

    def test_uno_ya_decidido_no_aparece(self):
        p = self._pago()
        DecisionSinBoleta.objects.create(pago=p)
        self.assertEqual(pagos_sin_resolver(self.venta), [])

    def test_una_devolucion_no_aparece(self):
        # No se boletea: se anula con nota de crédito, y esas van por el SII.
        self._pago(monto=-45000)
        self.assertEqual(pagos_sin_resolver(self.venta), [])

    def test_sin_medios_sembrados_no_inventa_pendientes(self):
        MedioPago.objects.all().delete()
        self._pago()
        self.assertEqual(pagos_sin_resolver(self.venta), [])


class LaPaginaDeDecision(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='admin_boleta', email='a@test.cl', password='x')
        MedioPago.objects.create(codigo='efectivo', nombre='Efectivo',
                                 genera_boleta=True, visible_al_cobrar=True)
        cls.cliente = Cliente.objects.create(nombre='Tomás', telefono='+56977777777')

    def setUp(self):
        self.client.force_login(self.staff)
        self.venta = VentaReserva.objects.create(cliente=self.cliente)
        self.pago = Pago.objects.create(venta_reserva=self.venta, monto=30000,
                                        metodo_pago='efectivo')
        self.url = reverse('facturacion:decidir_boleta_pago', args=[self.pago.pk])

    def test_muestra_la_pregunta(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn('¿Desea generar la boleta electrónica?', html)
        self.assertIn('$30.000', html)   # chileno, no "$30 000" del locale

    def test_el_no_queda_registrado_con_autor(self):
        self.client.post(self.url, {'emitir_boleta': 'no', 'motivo': 'ya tiene voucher'})
        d = DecisionSinBoleta.objects.get(pago=self.pago)
        self.assertEqual(d.usuario, self.staff)
        self.assertEqual(d.motivo, 'ya tiene voucher')

    def test_un_get_no_emite_nada(self):
        # Emitir es un acto tributario: un enlace que emitiera al abrirlo se
        # dispararía con el prefetch del navegador.
        self.client.get(self.url)
        self.assertFalse(BoletaElectronica.objects.exists())
        self.assertFalse(DecisionSinBoleta.objects.exists())

    def test_pide_sesion_de_staff(self):
        self.client.logout()
        r = self.client.get(self.url)
        self.assertIn(r.status_code, (302, 403))

    def test_si_ya_tiene_boleta_lo_dice_y_no_repregunta(self):
        BoletaElectronica.objects.create(pago=self.pago, venta_reserva=self.venta,
                                         folio=7, estado='aceptada',
                                         monto_total=30000, monto_neto=25210,
                                         monto_iva=4790)
        html = self.client.get(self.url).content.decode()
        self.assertIn('ya tiene boleta', html.lower())
        self.assertNotIn('¿Desea generar', html)


class ElAvisoAlGuardarEnElAdmin(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='admin_aviso', email='b@test.cl', password='x')
        MedioPago.objects.create(codigo='efectivo', nombre='Efectivo',
                                 genera_boleta=True, visible_al_cobrar=True)
        cls.cliente = Cliente.objects.create(nombre='Rita', telefono='+56988888888')

    def test_avisa_por_cada_pago_sin_resolver(self):
        from unittest.mock import MagicMock

        from ventas.admin import VentaReservaAdmin

        venta = VentaReserva.objects.create(cliente=self.cliente)
        Pago.objects.create(venta_reserva=venta, monto=15000, metodo_pago='efectivo')
        Pago.objects.create(venta_reserva=venta, monto=25000, metodo_pago='efectivo')

        adm = VentaReservaAdmin(VentaReserva, None)
        adm.message_user = MagicMock()
        request = MagicMock()
        request.get_full_path.return_value = '/admin/ventas/ventareserva/1/change/'

        adm._avisar_boletas_pendientes(request, venta)
        self.assertEqual(adm.message_user.call_count, 2)
        texto = str(adm.message_user.call_args[0][1])
        self.assertIn('Resolver ahora', texto)
        self.assertIn('/boletas/decidir/', texto)

    def test_no_avisa_si_no_hay_nada_pendiente(self):
        from unittest.mock import MagicMock

        from ventas.admin import VentaReservaAdmin

        venta = VentaReserva.objects.create(cliente=self.cliente)
        adm = VentaReservaAdmin(VentaReserva, None)
        adm.message_user = MagicMock()
        adm._avisar_boletas_pendientes(MagicMock(), venta)
        self.assertEqual(adm.message_user.call_count, 0)


class LosMontosSeVenALaChilena(TestCase):
    """El separador de miles lo pone `formato_clp`, no el locale de Django.

    Con `intcomma` los montos salían «$30 000» y «$1 087 500» (espacio) en vez
    de «$30.000» y «$1.087.500». Estaba así en las tres plantillas de
    facturación, incluida la página pública que se declaró al SII — donde un
    monto con formato raro es justo lo que hace dudar al cliente que la
    consulta.
    """

    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='fmt_admin', email='f@test.cl', password='x')
        MedioPago.objects.create(codigo='efectivo', nombre='Efectivo',
                                 genera_boleta=True, visible_al_cobrar=True)
        cls.cliente = Cliente.objects.create(nombre='Nico', telefono='+56999999999')

    def setUp(self):
        self.client.force_login(self.staff)

    def test_en_la_pagina_de_decision(self):
        venta = VentaReserva.objects.create(cliente=self.cliente)
        pago = Pago.objects.create(venta_reserva=venta, monto=1087500,
                                   metodo_pago='efectivo', usuario=self.staff)
        html = self.client.get(
            reverse('facturacion:decidir_boleta_pago', args=[pago.pk])).content.decode()
        self.assertIn('$1.087.500', html)
        self.assertNotIn('1 087 500', html)

    def test_en_el_listado_de_pendientes(self):
        venta = VentaReserva.objects.create(cliente=self.cliente)
        Pago.objects.create(venta_reserva=venta, monto=1087500,
                            metodo_pago='efectivo', usuario=self.staff)
        html = self.client.get(reverse('facturacion:pagos_sin_boleta')).content.decode()
        self.assertIn('$1.087.500', html)
        self.assertNotIn('1 087 500', html)

    def test_en_la_pagina_publica_del_cliente(self):
        b = BoletaElectronica.objects.create(
            pago=None, venta_reserva=None, ambiente='produccion', folio=90,
            estado='aceptada', monto_total=1087500, monto_neto=913025,
            monto_iva=174475)
        html = self.client.get(f'/boletas/b/{b.token_consulta}/').content.decode()
        self.assertIn('$1.087.500', html)
        self.assertNotIn('1 087 500', html)
