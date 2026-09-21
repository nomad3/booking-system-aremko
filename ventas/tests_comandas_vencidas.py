"""El proceso diario de comandas vencidas descuenta el stock Y cierra la comanda.

Se escribió en junio de 2026 y nunca estuvo agendado. La primera pasada real fue
la prueba de Jorge del 21-09-2026 desde cron-job.org: descontó 47 unidades de 37
comandas acumuladas desde agosto, y las dejó TODAS «pendientes». Al día siguiente
las volvería a encontrar, y cocina y la agenda las seguirían mostrando como si
faltara prepararlas.

Ejecutar:
    python manage.py test ventas.tests_comandas_vencidas
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ventas.models import (CategoriaProducto, Cliente, Comanda, DetalleComanda, Producto,
                           ReservaProducto, VentaReserva)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nombre='Marcela Prueba', telefono='+56911111130')
        cls.ampe = Producto.objects.create(
            nombre='Ampe', precio_base=15000, cantidad_disponible=14, venta_meson=True,
            categoria=CategoriaProducto.objects.create(nombre='Bebestibles'))

    def _comanda(self, hace_horas, cantidad=2, estado='pendiente'):
        v = VentaReserva.objects.create(cliente=self.cliente)
        rp = ReservaProducto.objects.create(venta_reserva=v, producto=self.ampe, cantidad=cantidad,
                                            precio_unitario_venta=Decimal('15000'))
        c = Comanda.objects.create(venta_reserva=v, estado=estado,
                                   fecha_entrega_objetivo=timezone.now() - datetime.timedelta(hours=hace_horas))
        DetalleComanda.objects.create(comanda=c, producto=self.ampe, cantidad=cantidad,
                                      precio_unitario=Decimal('15000'))
        return c, rp

    def _correr(self, **opts):
        salida = StringIO()
        call_command('procesar_entregas_comandas_vencidas', stdout=salida, **opts)
        return salida.getvalue()

    def _stock(self):
        self.ampe.refresh_from_db()
        return self.ampe.cantidad_disponible


class UnaComandaVencida(_Base):
    def test_descuenta_el_stock_y_la_cierra(self):
        c, rp = self._comanda(hace_horas=5)
        salida = self._correr()
        c.refresh_from_db(); rp.refresh_from_db()
        self.assertEqual(self._stock(), 12)
        self.assertEqual(rp.fecha_entrega, timezone.localdate())
        self.assertEqual(c.estado, 'entregada', 'antes quedaba pendiente para siempre')
        self.assertIsNotNone(c.fecha_entrega)
        self.assertIn('Dada por entregada automáticamente', c.notas_generales)
        self.assertIn('1 comanda(s) cerradas, 1 línea(s)', salida)

    def test_al_dia_siguiente_ya_no_la_encuentra(self):
        c, _ = self._comanda(hace_horas=5)
        self._correr()
        salida = self._correr()
        self.assertEqual(self._stock(), 12, 'no puede descontar dos veces')
        self.assertIn('0 comanda(s) cerradas', salida)

    def test_una_con_hora_objetivo_futura_no_se_toca(self):
        c, rp = self._comanda(hace_horas=-3)
        self._correr()
        c.refresh_from_db(); rp.refresh_from_db()
        self.assertEqual((c.estado, rp.fecha_entrega, self._stock()), ('pendiente', None, 14))

    def test_una_ya_entregada_a_mano_no_se_toca(self):
        c, rp = self._comanda(hace_horas=5, estado='entregada')
        ReservaProducto.objects.filter(pk=rp.pk).update(fecha_entrega=timezone.localdate() - datetime.timedelta(days=1))
        Producto.objects.filter(pk=self.ampe.pk).update(cantidad_disponible=12)
        self._correr()
        self.assertEqual(self._stock(), 12)

    def test_en_dry_run_no_cambia_nada(self):
        c, rp = self._comanda(hace_horas=5)
        self._correr(dry_run=True)
        c.refresh_from_db(); rp.refresh_from_db()
        self.assertEqual((c.estado, rp.fecha_entrega, self._stock()), ('pendiente', None, 14))

    def test_una_comanda_cancelada_no_cuenta(self):
        c, rp = self._comanda(hace_horas=5, estado='cancelada')
        self._correr()
        c.refresh_from_db()
        self.assertEqual((c.estado, self._stock()), ('cancelada', 14))
