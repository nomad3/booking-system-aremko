"""Los extras vendidos junto con una giftcard pasan A la giftcard.

Venta #6780 (07-09-2026): Pausa como giftcard ($110.000) más una ambientación
($32.000) colgada de la venta con fecha 02/02/2021, y un espumante de $0. El
total ($142.000) estaba bien para quien paga; la tarjeta no: quedó en
$110.000 y la carta no decía nada de la ambientación. Al canjear, alguien
tenía que acordarse de que los $32.000 vivían en otra venta con fecha del
2021.

Empaquetar mueve eso a la tarjeta: sube el monto, escribe los nombres en
«Incluye además» y saca las líneas de relleno. El total de la venta no cambia.

Ejecutar:
    python manage.py test ventas.tests_giftcard_empaquetado
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ventas.models import (CategoriaProducto, CategoriaServicio, Cliente, GiftCard,
                           Producto, ReservaProducto, ReservaServicio, Servicio,
                           VentaReserva)
from ventas.services.giftcard_empaquetado import (empaquetar, extras_de,
                                                  giftcard_destino)

RELLENO = datetime.date(2021, 2, 2)


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='deborah_t', email='d@test.cl', password='x')
        cls.cliente = Cliente.objects.create(nombre='Alexis', telefono='+56934823580')
        cls.ambientacion = Servicio.objects.create(
            nombre='Ambientación romántica R1', precio_base=32000,
            categoria=CategoriaServicio.objects.create(nombre='Otros'),
            duracion=0, tipo_servicio='otro', activo=True)
        cls.tina = Servicio.objects.create(
            nombre='Tina Hornopiren', precio_base=25000,
            categoria=CategoriaServicio.objects.create(nombre='Tinas'),
            duracion=120, tipo_servicio='tina', activo=True)
        cls.espumante = Producto.objects.create(
            nombre='1 Espumante', precio_base=0,
            categoria=CategoriaProducto.objects.create(nombre='Bebestibles'),
            cantidad_disponible=50, venta_meson=True)

    def _venta_6780(self):
        """La venta tal cual la dejó Deborah."""
        v = VentaReserva.objects.create(cliente=self.cliente)
        hoy = datetime.date.today()
        gc = GiftCard.objects.create(
            monto_inicial=110000, monto_disponible=110000, fecha_emision=hoy,
            fecha_vencimiento=hoy + datetime.timedelta(days=365),
            estado='por_cobrar', venta_reserva=v, destinatario_nombre='Fabiola',
            servicio_asociado='pausa_junto_al_rio')
        ReservaServicio.objects.create(
            venta_reserva=v, servicio=self.ambientacion, fecha_agendamiento=RELLENO,
            hora_inicio='19:00', cantidad_personas=1, precio_unitario_venta=32000)
        ReservaProducto.objects.create(
            venta_reserva=v, producto=self.espumante, cantidad=1,
            precio_unitario_venta=0)
        v.calcular_total(); v.save()
        return v, gc


class DetectarLosExtras(Base):
    def test_encuentra_la_ambientacion_de_relleno_y_el_espumante(self):
        v, _ = self._venta_6780()
        nombres = [e['nombre'] for e in extras_de(v)]
        self.assertEqual(nombres, ['Ambientación romántica R1', '1 Espumante'])

    def test_un_servicio_con_fecha_real_NO_es_un_extra(self):
        # Una reserva de verdad junto a una giftcard es una reserva de verdad.
        v, _ = self._venta_6780()
        ReservaServicio.objects.create(
            venta_reserva=v, servicio=self.tina,
            fecha_agendamiento=datetime.date.today() + datetime.timedelta(days=5),
            hora_inicio='14:00', cantidad_personas=2, precio_unitario_venta=25000)
        nombres = [e['nombre'] for e in extras_de(v)]
        self.assertNotIn('Tina Hornopiren', nombres)

    def test_sin_giftcard_no_hay_nada_que_empaquetar(self):
        v = VentaReserva.objects.create(cliente=self.cliente)
        ReservaServicio.objects.create(
            venta_reserva=v, servicio=self.ambientacion, fecha_agendamiento=RELLENO,
            hora_inicio='19:00', cantidad_personas=1, precio_unitario_venta=32000)
        self.assertEqual(extras_de(v), [])


class Empaquetar(Base):
    def test_la_tarjeta_sube_en_lo_que_valen_los_extras(self):
        v, gc = self._venta_6780()
        r = empaquetar(v, gc, self.staff)
        self.assertTrue(r['ok'], r)
        gc.refresh_from_db()
        self.assertEqual(int(gc.monto_inicial), 142000)
        self.assertEqual(int(gc.monto_disponible), 142000)

    def test_la_carta_va_a_decir_lo_que_incluye(self):
        v, gc = self._venta_6780()
        empaquetar(v, gc, self.staff)
        gc.refresh_from_db()
        self.assertEqual(gc.detalle_especial, 'Ambientación romántica R1, 1 Espumante')

    def test_las_lineas_de_relleno_salen_de_la_venta(self):
        v, gc = self._venta_6780()
        empaquetar(v, gc, self.staff)
        self.assertEqual(v.reservaservicios.count(), 0)
        self.assertEqual(v.reservaproductos.count(), 0)

    def test_el_total_de_la_venta_NO_cambia(self):
        # Alexis paga lo mismo antes y después: $142.000.
        v, gc = self._venta_6780()
        antes = int(v.total)
        empaquetar(v, gc, self.staff)
        v.refresh_from_db()
        self.assertEqual(int(v.total), antes)
        self.assertEqual(int(v.total), 142000)

    def test_deja_rastro_en_la_venta(self):
        v, gc = self._venta_6780()
        empaquetar(v, gc, self.staff)
        v.refresh_from_db()
        self.assertIn('Empaquetado en la giftcard', v.comentarios)
        self.assertIn('$110.000 a $142.000', v.comentarios)

    def test_deja_rastro_en_el_historial_de_la_giftcard(self):
        from django.contrib.admin.models import LogEntry
        v, gc = self._venta_6780()
        empaquetar(v, gc, self.staff)
        self.assertTrue(LogEntry.objects.filter(object_id=str(gc.pk)).exists())

    def test_respeta_lo_que_ya_decia_detalle_especial(self):
        v, gc = self._venta_6780()
        gc.detalle_especial = 'Tabla de quesos'
        gc.save()
        empaquetar(v, gc, self.staff)
        gc.refresh_from_db()
        self.assertEqual(gc.detalle_especial,
                         'Tabla de quesos, Ambientación romántica R1, 1 Espumante')

    def test_una_giftcard_de_otra_venta_se_rechaza(self):
        v, _ = self._venta_6780()
        otra_v, otra_gc = self._venta_6780()
        r = empaquetar(v, otra_gc, self.staff)
        self.assertFalse(r['ok'])
        self.assertEqual(v.reservaservicios.count(), 1, 'no debe tocar nada')

    def test_sin_extras_no_hace_nada(self):
        v, gc = self._venta_6780()
        empaquetar(v, gc, self.staff)
        r = empaquetar(v, gc, self.staff)      # segunda vez: ya no queda nada
        self.assertFalse(r['ok'])
        gc.refresh_from_db()
        self.assertEqual(int(gc.monto_inicial), 142000, 'no puede sumar dos veces')

    def test_todo_o_nada(self):
        # Si algo falla a mitad, la tarjeta no queda subida con las líneas
        # todavía en la venta (eso sería cobrar dos veces).
        from unittest.mock import patch
        v, gc = self._venta_6780()
        with patch.object(VentaReserva, 'calcular_total', side_effect=RuntimeError('BD')):
            with self.assertRaises(RuntimeError):
                empaquetar(v, gc, self.staff)
        gc.refresh_from_db()
        self.assertEqual(int(gc.monto_inicial), 110000)
        self.assertEqual(v.reservaservicios.count(), 1)


class DesdeElAdmin(Base):
    def setUp(self):
        self.client.force_login(self.staff)

    def _url(self, v):
        return reverse('admin:ventas_ventareserva_empaquetar_giftcard', args=[v.pk])

    def test_get_muestra_lo_que_va_a_pasar_sin_hacerlo(self):
        v, gc = self._venta_6780()
        r = self.client.get(self._url(v))
        html = r.content.decode()
        self.assertIn('Ambientación romántica R1', html)
        self.assertIn('142.000', html)
        gc.refresh_from_db()
        self.assertEqual(int(gc.monto_inicial), 110000, 'un GET no cambia nada')

    def test_post_empaqueta_y_vuelve_a_la_venta(self):
        v, gc = self._venta_6780()
        r = self.client.post(self._url(v))
        self.assertEqual(r.status_code, 302)
        gc.refresh_from_db()
        self.assertEqual(int(gc.monto_inicial), 142000)

    def test_la_venta_muestra_el_boton_cuando_hay_extras(self):
        v, _ = self._venta_6780()
        r = self.client.get(reverse('admin:ventas_ventareserva_change', args=[v.pk]))
        self.assertIn('Empaquetar en la giftcard', r.content.decode())

    def test_la_venta_NO_muestra_el_boton_si_no_hay_extras(self):
        v, gc = self._venta_6780()
        empaquetar(v, gc, self.staff)
        r = self.client.get(reverse('admin:ventas_ventareserva_change', args=[v.pk]))
        self.assertNotIn('Empaquetar en la giftcard', r.content.decode())

    def test_un_desconocido_no_puede(self):
        v, gc = self._venta_6780()
        self.client.logout()
        self.client.post(self._url(v))
        gc.refresh_from_db()
        self.assertEqual(int(gc.monto_inicial), 110000)


class AvisoAlGuardar(Base):
    def setUp(self):
        self.client.force_login(self.staff)

    def test_guardar_la_venta_con_extras_de_relleno_avisa(self):
        from ventas.admin import VentaReservaAdmin
        from django.contrib import admin as dj_admin
        from django.test import RequestFactory
        from django.contrib.messages.storage.fallback import FallbackStorage

        v, _ = self._venta_6780()
        req = RequestFactory().post('/')
        req.user = self.staff
        req.session = {}
        req._messages = FallbackStorage(req)
        VentaReservaAdmin(VentaReserva, dj_admin.site)._avisar_extras_sin_empaquetar(req, v)
        textos = [str(m) for m in req._messages]
        self.assertTrue(any('Empaquetar' in t for t in textos), textos)
