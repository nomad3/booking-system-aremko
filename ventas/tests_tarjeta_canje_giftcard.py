"""Pagar con gift card desde la tarjeta móvil (Jorge, 24-09-2026, «paso 1»).

Hasta hoy la tarjeta hacía todo el canje —crear la reserva, sumar servicios,
descuentos y pagos— menos lo único que lo distingue: pagar con la gift card.
Había que salir al admin a buscarla. En 90 días fueron 23 canjes, 22 a mano, y
en 10 de los 15 recientes la gift card no calzaba con el total (el cliente
agregó extras o la experiencia había subido de precio).

Ejecutar:
    python manage.py test ventas.tests_tarjeta_canje_giftcard
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.models import (CategoriaServicio, Cliente, GiftCard, Pago, Servicio,
                           VentaReserva)
from ventas.views.tarjeta_reserva_view import estado_giftcard


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='deborah_t', email='d@test.cl', password='x')
        cls.cliente = Cliente.objects.create(nombre='Natalia González', telefono='+56911112222')
        cls.tina = Servicio.objects.create(
            nombre='Tina Hornopiren', precio_base=25000, duracion=120,
            categoria=CategoriaServicio.objects.create(nombre='Tinas'),
            tipo_servicio='tina', activo=True, slots_disponibles={})

    def setUp(self):
        self.client.force_login(self.staff)
        self.venta = self._reserva()          # total $50.000

    def tearDown(self):
        from ventas import middleware
        middleware._thread_locals.user = None
        super().tearDown()

    def _reserva(self, personas=2):
        v = VentaReserva.objects.create(cliente=self.cliente)
        v.reservaservicios.create(
            servicio=self.tina, fecha_agendamiento=timezone.localdate(), hora_inicio='17:00',
            cantidad_personas=personas, precio_unitario_venta=Decimal('25000'))
        v.refresh_from_db()
        return v

    def _giftcard(self, monto=50000, saldo=None, estado='cobrado', vence_en=300, **extra):
        return GiftCard.objects.create(
            monto_inicial=monto, monto_disponible=monto if saldo is None else saldo,
            fecha_vencimiento=timezone.localdate() + datetime.timedelta(days=vence_en),
            estado=estado, servicio_asociado='tina_para_dos',
            destinatario_nombre='Natalia González', comprador_nombre='Claudia Carrasco', **extra)

    def _buscar(self, q, venta=None):
        return self.client.get(reverse('ventas:tarjeta_buscar_giftcard',
                                       args=[(venta or self.venta).pk]), {'q': q})

    def _aplicar(self, gc, venta=None, **extra):
        datos = {'giftcard_id': gc.pk}
        datos.update(extra)
        return self.client.post(reverse('ventas:tarjeta_aplicar_giftcard',
                                        args=[(venta or self.venta).pk]), datos)


class Buscar(_Base):
    def test_por_codigo_aunque_lo_dicten_en_minuscula_y_con_espacios(self):
        gc = self._giftcard()
        dictado = ' '.join([gc.codigo[:4], gc.codigo[4:8], gc.codigo[8:]]).lower()
        r = self._buscar(dictado)
        self.assertEqual(r.status_code, 200)
        [ficha] = r.json()['giftcards']
        self.assertEqual(ficha['codigo'], gc.codigo)
        self.assertEqual(ficha['aplicar'], 50000)
        self.assertEqual(ficha['para'], 'Natalia González')
        self.assertEqual(ficha['estado'], 'Lista para usar')

    def test_por_el_comienzo_del_codigo(self):
        gc = self._giftcard()
        [ficha] = self._buscar(gc.codigo[:7]).json()['giftcards']
        self.assertEqual(ficha['id'], gc.pk)

    def test_dictado_con_cero_donde_va_la_letra_o(self):
        # El caso real del 24-09: empieza con la LETRA O, y en el PDF se ve cero.
        gc = self._giftcard(codigo='OGEFH03K7B2J')
        [ficha] = self._buscar('0GEFH03K7B2J').json()['giftcards']
        self.assertEqual(ficha['id'], gc.pk)

    def test_y_al_reves_letra_o_donde_va_el_cero(self):
        gc = self._giftcard(codigo='OGEFH03K7B2J')
        [ficha] = self._buscar('OGEFHO3K7B2J').json()['giftcards']
        self.assertEqual(ficha['id'], gc.pk)

    def test_uno_donde_va_la_letra_i_y_viceversa(self):
        gc = self._giftcard(codigo='KI7XA1BCDEF2')
        [ficha] = self._buscar('K17XAIBCDEF2').json()['giftcards']
        self.assertEqual(ficha['id'], gc.pk)

    def test_tambien_con_el_comienzo_del_codigo(self):
        gc = self._giftcard(codigo='OGEFH03K7B2J')
        [ficha] = self._buscar('0gefh0').json()['giftcards']
        self.assertEqual(ficha['id'], gc.pk)

    def test_un_codigo_distinto_no_se_confunde(self):
        # Desde el 25-09 se toleran 1 o 2 caracteres mal leídos; 3 ya es otro código.
        self._giftcard(codigo='OGEFH03K7B2J')
        self.assertEqual(self._buscar('0GEFH03K7XXX').status_code, 404)

    def test_un_caracter_mal_copiado_la_encuentra_y_lo_avisa(self):
        # Caso real (20-09-2026): el código copiado a mano en una tarjeta de
        # cumpleaños, con un carácter mal; era la gift card 471.
        gc = self._giftcard(codigo='N7LTQ4ZX9PKA')
        r = self._buscar('N7LTQ4ZX9PKB')
        self.assertEqual(r.status_code, 200)
        [ficha] = r.json()['giftcards']
        self.assertEqual(ficha['id'], gc.pk)
        self.assertIn('1 carácter distinto', ficha['calce'])

    def test_dos_caracteres_mal_tambien(self):
        gc = self._giftcard(codigo='N7LTQ4ZX9PKA')
        [ficha] = self._buscar('N7LTQ4ZX9PBB').json()['giftcards']
        self.assertEqual(ficha['id'], gc.pk)
        self.assertIn('2 caracteres distintos', ficha['calce'])

    def test_el_calce_exacto_no_trae_aviso(self):
        gc = self._giftcard(codigo='N7LTQ4ZX9PKA')
        [ficha] = self._buscar(gc.codigo).json()['giftcards']
        self.assertNotIn('calce', ficha)

    def test_si_dos_quedan_igual_de_cerca_no_elige(self):
        self._giftcard(codigo='N7LTQ4ZX9PKA')
        self._giftcard(codigo='N7LTQ4ZX9PBB')
        self.assertEqual(self._buscar('N7LTQ4ZX9PKB').status_code, 404)

    def test_un_voucher_antiguo_dice_en_que_reserva_esta(self):
        antigua = VentaReserva.objects.create(id=5602, cliente=self.cliente)
        r = self._buscar('R 5602')
        self.assertEqual(r.status_code, 404)
        self.assertIn(f'reserva #{antigua.pk}', r.json()['mensaje'])
        self.assertIn('voucher antiguo', r.json()['mensaje'])

    def test_un_voucher_sin_reserva_es_un_no_encontrado_normal(self):
        r = self._buscar('R 9876')
        self.assertEqual(r.status_code, 404)
        self.assertIn('No encontré', r.json()['mensaje'])

    def test_por_el_nombre_de_quien_la_recibio(self):
        gc = self._giftcard()
        [ficha] = self._buscar('natalia').json()['giftcards']
        self.assertEqual(ficha['id'], gc.pk)

    def test_por_nombre_no_aparecen_las_usadas_ni_las_vencidas(self):
        self._giftcard(saldo=0)
        self._giftcard(vence_en=-1)
        r = self._buscar('natalia')
        self.assertEqual(r.status_code, 404)

    def test_un_codigo_que_no_existe_lo_dice(self):
        r = self._buscar('ZZZZ9999ZZZZ')
        self.assertEqual(r.status_code, 404)
        self.assertIn('No encontré', r.json()['mensaje'])

    def test_buscar_no_toca_nada(self):
        gc = self._giftcard()
        self._buscar(gc.codigo)
        gc.refresh_from_db()
        self.assertEqual(gc.monto_disponible, 50000)
        self.assertFalse(Pago.objects.exists())


class Aplicar(_Base):
    def test_paga_la_reserva_y_descuenta_la_gift_card(self):
        gc = self._giftcard()
        r = self._aplicar(gc)
        self.assertTrue(r.json()['ok'], r.json())
        pago = Pago.objects.get(venta_reserva=self.venta)
        self.assertEqual((pago.metodo_pago, int(pago.monto), pago.giftcard_id, pago.usuario_id),
                         ('giftcard', 50000, gc.pk, self.staff.pk))
        self.venta.refresh_from_db(); gc.refresh_from_db()
        self.assertEqual(int(self.venta.saldo_pendiente), 0)
        self.assertEqual(int(gc.monto_disponible), 0)
        self.assertEqual(estado_giftcard(gc), 'Usada')

    def test_si_la_gift_card_no_alcanza_aplica_todo_su_saldo_y_dice_cuanto_falta(self):
        gc = self._giftcard(monto=40000)
        r = self._aplicar(gc)
        self.assertIn('Faltan $10.000', r.json()['mensaje'])
        self.assertIn('Aplicar descuento', r.json()['mensaje'])
        self.venta.refresh_from_db()
        self.assertEqual(int(self.venta.saldo_pendiente), 10000)

    def test_si_sobra_solo_aplica_lo_que_falta_y_la_gift_card_guarda_el_resto(self):
        gc = self._giftcard(monto=80000)
        r = self._aplicar(gc)
        self.assertIn('le quedan $30.000', r.json()['mensaje'])
        gc.refresh_from_db()
        self.assertEqual(int(gc.monto_disponible), 30000)
        self.assertEqual(estado_giftcard(gc), 'Le quedan $30.000')

    def test_el_segundo_clic_no_cobra_dos_veces(self):
        gc = self._giftcard()
        self.assertTrue(self._aplicar(gc).json()['ok'])
        r = self._aplicar(gc)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Pago.objects.filter(venta_reserva=self.venta).count(), 1)

    def test_una_vencida_no_se_aplica(self):
        gc = self._giftcard(vence_en=-1)
        r = self._aplicar(gc)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Venció', r.json()['mensaje'])
        self.assertFalse(Pago.objects.exists())

    def test_una_ya_usada_dice_en_que_reserva(self):
        gc = self._giftcard()
        otra = self._reserva()
        self.assertTrue(self._aplicar(gc, venta=otra).json()['ok'])
        r = self._aplicar(gc)
        self.assertEqual(r.status_code, 400)
        self.assertIn(f'reserva #{otra.pk}', r.json()['mensaje'])

    def test_una_reserva_sin_saldo_por_pagar_no_la_gasta(self):
        Pago.objects.create(venta_reserva=self.venta, monto=50000, metodo_pago='efectivo')
        gc = self._giftcard()
        r = self._aplicar(gc)
        self.assertEqual(r.status_code, 400)
        self.assertIn('no tiene saldo', r.json()['mensaje'])
        gc.refresh_from_db()
        self.assertEqual(int(gc.monto_disponible), 50000)

    def test_no_puede_pagar_la_misma_reserva_donde_se_vendio(self):
        gc = self._giftcard(venta_reserva=self.venta)
        self.venta.refresh_from_db()
        r = self._aplicar(gc)
        self.assertEqual(r.status_code, 400)
        self.assertIn('ESTA reserva', r.json()['mensaje'])


class LaCompraSinPagar(_Base):
    """«¿Se pagó?» se lee de la venta donde se compró, no del campo `estado`,
    que significa dos cosas (compra sin pagar / vigente con saldo)."""

    def _venta_de_giftcard(self, pagada, monto=50000):
        """Una VENTA de gift card como la arman Luna o la web: la gift card es
        lo que se vende, y el total de la venta es su monto."""
        from unittest import mock
        venta = VentaReserva.objects.create(cliente=self.cliente)
        gc = self._giftcard(monto=monto, estado='por_cobrar', venta_reserva=venta)
        venta.calcular_total()
        venta.refresh_from_db()
        if pagada:
            # Al pagarse, la señal la marca «cobrado» y manda el PDF por email;
            # el correo no es el sujeto de estas pruebas.
            with mock.patch('ventas.signals.giftcard_signals.enviar_email_giftcards'):
                Pago.objects.create(venta_reserva=venta, monto=venta.total, metodo_pago='efectivo')
            gc.refresh_from_db()
        return venta, gc

    def test_si_la_venta_de_origen_debe_se_pregunta_antes(self):
        origen, gc = self._venta_de_giftcard(pagada=False)
        r = self._aplicar(gc)
        self.assertEqual(r.status_code, 409)
        self.assertTrue(r.json()['confirmar'])
        self.assertIn(f'reserva #{origen.pk}', r.json()['mensaje'])
        self.assertIn('debe $50.000', r.json()['mensaje'])
        self.assertFalse(Pago.objects.filter(venta_reserva=self.venta).exists())

    def test_confirmando_se_aplica_sin_tocar_el_estado(self):
        origen, gc = self._venta_de_giftcard(pagada=False, monto=80000)
        r = self._aplicar(gc, confirmar_por_cobrar='1')
        self.assertTrue(r.json()['ok'], r.json())
        gc.refresh_from_db()
        self.assertEqual(int(gc.monto_disponible), 30000)

    def test_la_de_venta_pagada_no_pregunta(self):
        origen, gc = self._venta_de_giftcard(pagada=True)
        self.assertEqual(gc.estado, 'cobrado', 'la señal de la venta la marcó pagada')
        r = self._aplicar(gc)
        self.assertTrue(r.json()['ok'], r.json())

    def test_la_de_venta_pagada_no_pregunta_aunque_diga_por_cobrar(self):
        # 4 así en prod el 24-09: pagadas, pero un canje parcial o un ajuste de
        # saldo las dejó en «por_cobrar».
        origen, gc = self._venta_de_giftcard(pagada=True)
        GiftCard.objects.filter(pk=gc.pk).update(estado='por_cobrar')
        r = self._aplicar(gc)
        self.assertTrue(r.json()['ok'], r.json())

    def test_la_vendida_a_mano_sin_venta_ligada_no_pregunta(self):
        gc = self._giftcard(estado='por_cobrar')       # como las del admin
        r = self._aplicar(gc)
        self.assertTrue(r.json()['ok'], r.json())


class LaPantalla(_Base):
    def test_la_tarjeta_ofrece_el_boton(self):
        html = self.client.get(reverse('ventas:tarjeta_reserva', args=[self.venta.pk])).content.decode()
        self.assertIn('Pagar con gift card', html)

    def test_la_lista_de_pagos_muestra_que_gift_card_se_uso(self):
        gc = self._giftcard()
        self._aplicar(gc)
        html = self.client.get(reverse('ventas:tarjeta_reserva', args=[self.venta.pk])).content.decode()
        self.assertIn(gc.codigo, html)

    def test_solo_el_equipo_puede_buscar_y_aplicar(self):
        gc = self._giftcard()
        self.client.logout()
        cualquiera = get_user_model().objects.create_user(username='visita', password='x')
        self.client.force_login(cualquiera)
        self.assertNotEqual(self._buscar(gc.codigo).status_code, 200)
        self.assertNotEqual(self._aplicar(gc).status_code, 200)
        self.assertFalse(Pago.objects.exists())


class ElEstadoEnPalabras(_Base):
    def test_cada_caso(self):
        casos = [
            (dict(), 'Lista para usar'),
            (dict(estado='por_cobrar'), 'Lista para usar'),   # sin venta ligada
            (dict(monto=50000, saldo=20000), 'Le quedan $20.000'),
            (dict(saldo=0), 'Usada'),
            (dict(vence_en=-1), 'Vencida'),
        ]
        for datos, esperado in casos:
            with self.subTest(esperado=esperado):
                self.assertEqual(estado_giftcard(self._giftcard(**datos)), esperado)

    def test_por_cobrar_es_cuando_la_venta_de_origen_debe(self):
        gc = self._giftcard(estado='cobrado', venta_reserva=self._reserva())
        self.assertEqual(estado_giftcard(gc), 'Por cobrar')
