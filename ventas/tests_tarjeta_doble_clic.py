"""Un clic, un pago. Un clic, un producto.

Domingo 20-09-2026, computador de recepción:

· Reserva 6869: un pago de $58.000 quedó registrado DOS veces con 0,2 segundos de
  diferencia. El servidor corre 3 procesos en paralelo; cada uno tomó un clic, los
  dos preguntaron «¿hay un pago igual reciente?» antes de que el otro guardara, y
  los dos guardaron. La guarda del 04-09 no servía contra pedidos simultáneos.
· Reserva 6865: $3.000 en efectivo con boleta. La emisión al SII tardó 9 segundos
  sin ninguna señal en pantalla; Ernesto apretó de nuevo, la guarda SÍ preguntó, y
  aceptó por reflejo. Dos boletas reales, folios 69078 y 69079.
· Misma 6865: cada doble clic en «Agregar producto» dejó dos líneas iguales y, para
  cocina, comandas con el doble de unidades o dos comandas gemelas.

Tres defensas: el botón se bloquea al primer clic, el servidor atiende de a un
pedido por reserva, y un pago calcado a menos de 30 segundos se rechaza sin preguntar.

Ejecutar:
    python manage.py test ventas.tests_tarjeta_doble_clic
"""
from __future__ import annotations

import datetime
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.models import (CategoriaProducto, CategoriaServicio, Cliente, Comanda, Pago, Producto,
                           ReservaProducto, Servicio, VentaReserva)
from ventas.views import tarjeta_reserva_view as vista


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='ernesto_t', email='e@test.cl', password='x')
        cls.cliente = Cliente.objects.create(nombre='Candela Prueba', telefono='+5491100000000')
        cls.tina = Servicio.objects.create(
            nombre='Tina Hornopiren', precio_base=25000, duracion=120,
            categoria=CategoriaServicio.objects.create(nombre='Tinas'),
            tipo_servicio='tina', activo=True, slots_disponibles={})
        cls.ampe = Producto.objects.create(
            nombre='Ampe', precio_base=15000, cantidad_disponible=20, venta_meson=True,
            categoria=CategoriaProducto.objects.create(nombre='Bebestibles'))

    def setUp(self):
        self.client.force_login(self.staff)
        self.venta = VentaReserva.objects.create(cliente=self.cliente)
        self.venta.reservaservicios.create(
            servicio=self.tina, fecha_agendamiento=timezone.localdate(), hora_inicio='17:00',
            cantidad_personas=2, precio_unitario_venta=Decimal('25000'))

    def tearDown(self):
        from ventas import middleware
        middleware._thread_locals.user = None
        super().tearDown()

    def _cobrar(self, monto='58000', metodo='tarjeta', **extra):
        datos = {'monto': monto, 'metodo_pago': metodo}
        datos.update(extra)
        return self.client.post(reverse('ventas:tarjeta_agregar_pago', args=[self.venta.pk]), datos)

    def _agregar(self, producto, cantidad=1):
        return self.client.post(reverse('ventas:tarjeta_agregar_producto', args=[self.venta.pk]),
                                {'producto_id': producto.pk, 'cantidad': cantidad})


class UnPagoCalcadoARecienHechoSeRechaza(_Base):
    def test_la_6869_el_segundo_clic_no_guarda_otro_pago(self):
        self.assertTrue(self._cobrar().json()['ok'])
        r = self._cobrar()
        self.assertEqual(r.status_code, 409)
        self.assertTrue(r.json()['duplicado'])
        self.assertNotIn('repetido', r.json(), 'no se pregunta: una pregunta se acepta por reflejo')
        self.assertIn('ya quedó registrado', r.json()['mensaje'])
        self.assertEqual(Pago.objects.filter(venta_reserva=self.venta).count(), 1)

    def test_la_6865_aceptar_la_pregunta_a_los_9_segundos_tampoco_lo_guarda(self):
        self._cobrar(monto='3000', metodo='efectivo')
        Pago.objects.update(fecha_pago=timezone.now() - datetime.timedelta(seconds=9))
        r = self._cobrar(monto='3000', metodo='efectivo', confirmar_repetido='1')
        self.assertTrue(r.json()['duplicado'])
        self.assertEqual(Pago.objects.filter(venta_reserva=self.venta).count(), 1)

    def test_pasado_el_medio_minuto_se_pregunta_y_confirmando_se_guarda(self):
        self._cobrar()
        Pago.objects.update(fecha_pago=timezone.now() - datetime.timedelta(seconds=45))
        r = self._cobrar()
        self.assertTrue(r.json()['repetido'])
        self.assertNotIn('duplicado', r.json())
        self.assertTrue(self._cobrar(confirmar_repetido='1').json()['ok'])
        self.assertEqual(Pago.objects.filter(venta_reserva=self.venta).count(), 2)

    def test_otro_monto_u_otro_medio_al_tiro_si_pasa(self):
        # Dos personas que se reparten la cuenta con montos distintos, o mitad tarjeta
        # y mitad efectivo: eso no es un doble clic.
        self._cobrar(monto='58000', metodo='tarjeta')
        self.assertTrue(self._cobrar(monto='8500', metodo='tarjeta').json()['ok'])
        self.assertTrue(self._cobrar(monto='58000', metodo='efectivo').json()['ok'])
        self.assertEqual(Pago.objects.filter(venta_reserva=self.venta).count(), 3)

    def test_el_mensaje_dice_que_hacer_si_de_verdad_es_otro_pago(self):
        self._cobrar()
        self.assertIn('espera un momento', self._cobrar().json()['mensaje'])


class ElServidorAtiendeDeAUnPedidoPorReserva(_Base):
    def _espia(self):
        entradas = []

        @contextmanager
        def falso(venta_id):
            entradas.append(venta_id)
            yield
        return entradas, falso

    def test_el_pago_se_revisa_y_se_guarda_bajo_candado(self):
        entradas, falso = self._espia()
        with patch.object(vista, '_reserva_en_exclusiva', falso):
            self._cobrar()
        self.assertEqual(entradas, [self.venta.pk])

    def test_el_producto_y_su_comanda_van_bajo_candado(self):
        entradas, falso = self._espia()
        with patch.object(vista, '_reserva_en_exclusiva', falso):
            self._agregar(self.ampe, 2)
        self.assertEqual(entradas, [self.venta.pk])

    def test_el_candado_es_consultivo_y_NO_abre_una_transaccion(self):
        # Con una transacción, un error de base que la cadena de señales del pago se
        # traga (el aviso a un cliente sin correo) deja la transacción inválida y el
        # pago se pierde. Lo destapó la prueba contra Postgres real, antes de salir.
        import inspect
        fuente = inspect.getsource(vista._reserva_en_exclusiva)
        codigo = fuente.split('"""')[2]          # sin el docstring, que sí nombra la transacción
        self.assertIn('pg_try_advisory_lock', codigo)
        self.assertIn('pg_advisory_unlock', codigo)
        self.assertNotIn('atomic', codigo)
        self.assertNotIn('select_for_update', codigo)

    def test_en_fila_cada_pedido_ve_lo_que_hizo_el_anterior(self):
        # Lo que el candado garantiza: los dos clics se atienden uno después del otro.
        # Así cada uno manda a cocina SUS unidades, no «todo lo que falta» dos veces
        # (6865: dos comandas de «Ampe x2» en el mismo segundo por 2 unidades vendidas).
        self._agregar(self.ampe, 1)
        self._agregar(self.ampe, 1)
        comandas = Comanda.objects.filter(venta_reserva=self.venta).order_by('id')
        self.assertEqual([c.detalles.get().cantidad for c in comandas], [1, 1])
        vendidas = sum(ReservaProducto.objects.filter(venta_reserva=self.venta)
                       .values_list('cantidad', flat=True))
        en_cocina = sum(d.cantidad for c in comandas for d in c.detalles.all())
        self.assertEqual(vendidas, en_cocina, 'cocina no puede recibir más de lo vendido')

    def test_si_la_comanda_falla_el_producto_queda_igual(self):
        with patch('ventas.services.comanda_productos.asegurar_comanda_de_productos',
                   side_effect=RuntimeError('cocina caída')):
            datos = self._agregar(self.ampe).json()
        self.assertTrue(datos['ok'])
        self.assertIsNone(datos['comanda'])
        self.assertTrue(ReservaProducto.objects.filter(venta_reserva=self.venta).exists())


class ElBotonSeBloqueaAlPrimerClic(_Base):
    def setUp(self):
        super().setUp()
        self.html = self.client.get(
            reverse('ventas:tarjeta_reserva', args=[self.venta.pk])).content.decode()

    def test_el_de_pago(self):
        self.assertIn('if (botonPago.disabled) { return; }', self.html)
        self.assertIn("botonPago.textContent = 'Registrando…';", self.html)

    def test_el_de_producto(self):
        self.assertIn('if (botonProd.disabled) { return; }', self.html)
        self.assertIn("botonProd.textContent = 'Agregando…';", self.html)

    def test_un_pago_calcado_se_avisa_sin_preguntar(self):
        antes_de_preguntar = self.html.index('if (d.duplicado)')
        self.assertLess(antes_de_preguntar, self.html.index('if (d.repetido)'))

    def test_el_boton_se_suelta_en_todos_los_finales(self):
        # Un botón que queda bloqueado para siempre es peor que el doble clic.
        self.assertGreaterEqual(self.html.count('soltarPago()'), 3)
        self.assertGreaterEqual(self.html.count('soltarProd()'), 2)
