# -*- coding: utf-8 -*-
"""Tests de artesanías. Las señales CRM/Meta de VentaReserva se desconectan
(patrón de la casa: esas señales requieren tablas del drift AR-033/034 que el
shim de tests no migra)."""
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db.models.signals import post_save
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ArtesaniaPieza, producto_generico
from .services import ErrorVenta, vender_pieza


def _sensores():
    """Los mismos que desconecta tests_checkout_agenda (tablas del drift)."""
    from control_gestion.signals import react_to_reserva_change
    from ventas.signals.main_signals import actualizar_tramo_y_premios_on_pago
    return (actualizar_tramo_y_premios_on_pago, react_to_reserva_change)


def _sin_senales_reserva():
    from ventas.models import VentaReserva
    for r in _sensores():
        post_save.disconnect(r, sender=VentaReserva)


def _con_senales_reserva():
    from ventas.models import VentaReserva
    for r in _sensores():
        post_save.connect(r, sender=VentaReserva)


def _reserva_minima():
    from ventas.models import Cliente, VentaReserva
    cliente = Cliente.objects.create(nombre='Cliente Prueba', telefono='+56900000001')
    return VentaReserva.objects.create(cliente=cliente,
                                       fecha_reserva=timezone.now())


class VenderPiezaTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _sin_senales_reserva()

    @classmethod
    def tearDownClass(cls):
        _con_senales_reserva()
        super().tearDownClass()

    def setUp(self):
        self.pieza = ArtesaniaPieza.objects.create(
            codigo='45', nombre='Tabla cuadrada', precio=20000)

    def test_venta_crea_linea_real_y_marca_la_pieza(self):
        reserva = _reserva_minima()
        pieza, r = vender_pieza('45', reserva.id)

        # La línea existe con el precio REAL de la pieza (no unidades de mil).
        linea = r.reservaproductos.get()
        self.assertEqual(int(linea.precio_unitario_venta), 20000)
        self.assertEqual(linea.cantidad, 1)
        self.assertEqual(linea.producto.nombre, 'Artesanía (pieza única)')
        self.assertIsNotNone(linea.fecha_entrega)

        # El total de la reserva se actualizó.
        r.refresh_from_db()
        self.assertEqual(int(r.total), 20000)

        # La pieza quedó vendida y enlazada.
        pieza.refresh_from_db()
        self.assertEqual(pieza.estado, 'vendida')
        self.assertEqual(pieza.venta_reserva_id, r.id)
        self.assertEqual(int(pieza.venta_monto), 20000)

    def test_no_se_vende_dos_veces_ni_a_reserva_inexistente(self):
        reserva = _reserva_minima()
        vender_pieza('45', reserva.id)
        with self.assertRaises(ErrorVenta):
            vender_pieza('45', reserva.id)
        with self.assertRaises(ErrorVenta):
            vender_pieza('999', reserva.id)

        pieza2 = ArtesaniaPieza.objects.create(
            codigo='58', nombre='Telar', precio=8000)
        with self.assertRaises(ErrorVenta):
            vender_pieza('58', 999999)
        pieza2.refresh_from_db()
        self.assertEqual(pieza2.estado, 'disponible')   # nada quedó a medias

    def test_monto_ajustado_manda_sobre_precio_lista(self):
        reserva = _reserva_minima()
        vender_pieza('45', reserva.id, monto=15000)
        reserva.refresh_from_db()
        self.assertEqual(int(reserva.total), 15000)


class CargaCatalogoTest(TestCase):
    def test_carga_idempotente_y_estados(self):
        call_command('cargar_catalogo_artesanias')          # lectura
        self.assertEqual(ArtesaniaPieza.objects.count(), 0)

        call_command('cargar_catalogo_artesanias', '--aplicar')
        total = ArtesaniaPieza.objects.count()
        self.assertEqual(total, 145)
        self.assertEqual(ArtesaniaPieza.objects.filter(
            estado__in=ArtesaniaPieza.VIVOS).count(), 66)   # 61 sala + 5 bodega
        # Una vendida histórica quedó con su venta anotada.
        p = ArtesaniaPieza.objects.get(codigo='755')
        self.assertEqual(p.estado, 'vendida')
        self.assertEqual(int(p.venta_monto), 35000)
        # El código duplicado del papel quedó diferenciado.
        self.assertTrue(ArtesaniaPieza.objects.filter(codigo='781B').exists())
        # Idempotente.
        call_command('cargar_catalogo_artesanias', '--aplicar')
        self.assertEqual(ArtesaniaPieza.objects.count(), total)
        # El producto genérico existe y es UNO solo.
        from ventas.models import Producto
        self.assertEqual(Producto.objects.filter(
            nombre='Artesanía (pieza única)').count(), 1)

    def test_siguiente_codigo_continua_el_papel(self):
        call_command('cargar_catalogo_artesanias', '--aplicar')
        self.assertEqual(ArtesaniaPieza.siguiente_codigo(), '1061')


class CatalogoVistaTest(TestCase):
    def test_solo_staff(self):
        self.assertEqual(self.client.get(
            reverse('artesanias:catalogo')).status_code, 302)

    def test_staff_ve_catalogo_y_alta_rapida(self):
        User.objects.create_user('recepcion', password='x', is_staff=True)
        self.client.login(username='recepcion', password='x')
        ArtesaniaPieza.objects.create(codigo='45', nombre='Tabla', precio=20000)

        r = self.client.get(reverse('artesanias:catalogo'))
        self.assertContains(r, 'Tabla')
        self.assertContains(r, 'Vender')

        # Alta rápida crea la pieza.
        self.client.post(reverse('artesanias:catalogo'), {
            'accion': 'alta', 'codigo': '1061', 'nombre': 'Bandeja nueva',
            'precio': '25.000', 'estado': 'disponible'})
        self.assertTrue(ArtesaniaPieza.objects.filter(codigo='1061').exists())
        # Código repetido no pasa.
        self.client.post(reverse('artesanias:catalogo'), {
            'accion': 'alta', 'codigo': '1061', 'nombre': 'Otra', 'precio': '1000'})
        self.assertEqual(ArtesaniaPieza.objects.filter(codigo='1061').count(), 1)


class DeshacerVentaTest(TestCase):
    """Al eliminar la línea (o la reserva), la pieza vuelve sola a disponible."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _sin_senales_reserva()

    @classmethod
    def tearDownClass(cls):
        _con_senales_reserva()
        super().tearDownClass()

    def test_borrar_la_linea_devuelve_la_pieza(self):
        ArtesaniaPieza.objects.create(codigo='45', nombre='Tabla', precio=20000)
        reserva = _reserva_minima()
        pieza, r = vender_pieza('45', reserva.id)
        linea = r.reservaproductos.get()
        self.assertEqual(pieza.venta_linea_id, linea.id)

        linea.delete()

        pieza.refresh_from_db()
        self.assertEqual(pieza.estado, 'disponible')
        self.assertIsNone(pieza.venta_reserva)
        self.assertIsNone(pieza.venta_monto)
        self.assertIsNone(pieza.venta_linea)
        self.assertIn('deshecha', pieza.notas)
        # Y el total de la reserva volvió a cero (señal post_delete de ventas).
        r.refresh_from_db()
        self.assertEqual(int(r.total), 0)
        # Se puede volver a vender.
        vender_pieza('45', reserva.id)

    def test_borrar_la_reserva_entera_tambien_devuelve(self):
        ArtesaniaPieza.objects.create(codigo='58', nombre='Telar', precio=8000)
        reserva = _reserva_minima()
        pieza, _ = vender_pieza('58', reserva.id)
        reserva.delete()
        pieza.refresh_from_db()
        self.assertEqual(pieza.estado, 'disponible')
        self.assertIsNone(pieza.venta_linea)
