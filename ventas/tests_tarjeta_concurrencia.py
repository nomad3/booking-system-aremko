"""Dos clics AL MISMO TIEMPO, de verdad: dos hilos contra Postgres.

Las demás pruebas del doble clic mandan un pedido después del otro. El problema del
20-09-2026 fue otro: dos pedidos SIMULTÁNEOS, cada uno en su proceso (el servidor
corre 3). Eso solo se puede reproducir con una base que tenga candados de fila; en
sqlite `select_for_update` no hace nada, así que ahí esta prueba se salta.

Para correrla hace falta un settings que apunte al Postgres de docker y cree el
esquema desde los modelos (no se commitea, igual que el de sqlite, por el drift
AR-033/034). `aremko_project/test_settings_pg.py`:

    from .settings import *
    class _SinMigraciones(dict):
        def __contains__(self, item): return True
        def __getitem__(self, item): return None
    MIGRATION_MODULES = _SinMigraciones()
    DATABASES['default'].setdefault('TEST', {})['NAME'] = 'test_concurrencia_tarjeta'

    docker compose run --rm --entrypoint "" web python manage.py test \\
        ventas.tests_tarjeta_concurrencia --settings=aremko_project.test_settings_pg --noinput

Verificada rompiendo (21-09-2026): con el candado apagado falla; con el candado, pasa.
La PRIMERA versión del candado (una transacción con select_for_update) también falló
acá: el pago de un cliente sin correo se perdía. Por eso el candado es consultivo.
"""
from __future__ import annotations

import threading
from decimal import Decimal
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from ventas.models import (CategoriaProducto, CategoriaServicio, Cliente, Comanda, Pago, Producto,
                           ReservaProducto, Servicio, VentaReserva)


@skipUnless(connection.vendor == 'postgresql', 'el candado de fila solo existe en Postgres')
class DosClicsALaVez(TransactionTestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_superuser(
            username='ernesto_c', email='ec@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Candela Prueba', telefono='+5491100000001')
        tina = Servicio.objects.create(
            nombre='Tina Hornopiren', precio_base=25000, duracion=120,
            categoria=CategoriaServicio.objects.create(nombre='Tinas'),
            tipo_servicio='tina', activo=True, slots_disponibles={})
        self.ampe = Producto.objects.create(
            nombre='Ampe', precio_base=15000, cantidad_disponible=20, venta_meson=True,
            categoria=CategoriaProducto.objects.create(nombre='Bebestibles'))
        self.venta = VentaReserva.objects.create(cliente=cliente)
        self.venta.reservaservicios.create(
            servicio=tina, fecha_agendamiento=timezone.localdate(), hora_inicio='17:00',
            cantidad_personas=2, precio_unitario_venta=Decimal('25000'))

    def tearDown(self):
        from ventas import middleware
        middleware._thread_locals.user = None

    def _a_la_vez(self, url, datos, n=2):
        """Dispara `n` POST idénticos en el mismo instante y devuelve las respuestas."""
        barrera = threading.Barrier(n)
        respuestas = [None] * n

        def clic(i):
            cliente = Client()
            cliente.force_login(self.staff)
            barrera.wait()
            try:
                r = cliente.post(url, datos)
                respuestas[i] = (r.status_code, r.json())
            finally:
                connection.close()

        hilos = [threading.Thread(target=clic, args=(i,)) for i in range(n)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=60)
        return respuestas

    def test_doble_clic_en_guardar_pago_deja_UN_pago(self):
        respuestas = self._a_la_vez(reverse('ventas:tarjeta_agregar_pago', args=[self.venta.pk]),
                                    {'monto': '58000', 'metodo_pago': 'tarjeta'})
        self.assertEqual(Pago.objects.filter(venta_reserva=self.venta).count(), 1, respuestas)
        self.assertEqual(sorted(r[0] for r in respuestas), [200, 409], respuestas)
        rechazado = next(r[1] for r in respuestas if r[0] == 409)
        self.assertTrue(rechazado.get('duplicado'), rechazado)

    def test_triple_clic_tambien(self):
        # Pasó de verdad: reserva 6187, 03-07-2026, el mismo pago TRES veces.
        self._a_la_vez(reverse('ventas:tarjeta_agregar_pago', args=[self.venta.pk]),
                       {'monto': '10000', 'metodo_pago': 'tarjeta'}, n=3)
        self.assertEqual(Pago.objects.filter(venta_reserva=self.venta).count(), 1)

    def test_doble_clic_en_agregar_producto_no_infla_lo_que_va_a_cocina(self):
        self._a_la_vez(reverse('ventas:tarjeta_agregar_producto', args=[self.venta.pk]),
                       {'producto_id': self.ampe.pk, 'cantidad': 2})
        vendidas = sum(ReservaProducto.objects.filter(venta_reserva=self.venta)
                       .values_list('cantidad', flat=True))
        en_cocina = sum(d.cantidad for c in Comanda.objects.filter(venta_reserva=self.venta)
                        for d in c.detalles.all())
        self.assertEqual(en_cocina, vendidas,
                         'cocina recibía el doble: dos comandas de «Ampe x2» por 2 unidades')
