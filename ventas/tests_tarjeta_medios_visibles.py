"""El selector de pago de la tarjeta muestra lo MISMO que el admin.

Bug encontrado por Jorge el 04-09-2026, mirando el menú en su teléfono: «no
será que el menú del celular es distinto del de la versión de PC? porque
habíamos ocultado varias de las cuentas que aparecen visibles acá».

Tenía razón. La tarjeta armaba su lista directo de `Pago.METODOS_PAGO` y se
saltaba el interruptor `visible_al_cobrar`: 20 opciones donde el admin
mostraba 11, con las cuentas personales que se ocultaron en agosto adentro.

No era cosmético. «Transferencia a Mercado Pago» quedaba en la posición 16 de
20, y quien cobraba elegía «MercadoPago» —posición 6, y NO boletea— para
registrar transferencias. Por eso Deborah reportó que al pagar una
transferencia no le aparecía la pregunta de la boleta.

Ejecutar:
    python manage.py test ventas.tests_tarjeta_medios_visibles
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from facturacion.models import MedioPago
from ventas.models import Cliente, VentaReserva
from ventas.views.tarjeta_reserva_view import METODOS_PAGO_TARJETA


class ElSelectorRespetaLoQueSeOculto(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='cajera_medios', email='s@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Ana', telefono='+56933333333')
        cls.venta = VentaReserva.objects.create(cliente=cliente)

    def setUp(self):
        self.client.force_login(self.staff)
        MedioPago.objects.all().delete()
        from django.core.cache import cache
        cache.clear()

    def _codigos_del_selector(self):
        r = self.client.get(reverse('ventas:tarjeta_reserva', args=[self.venta.pk]))
        return [c for c, _ in r.context['metodos_pago']]

    def _sembrar(self, visibles, ocultos=()):
        for c in visibles:
            MedioPago.objects.create(codigo=c, nombre=c, visible_al_cobrar=True,
                                     genera_boleta=False)
        for c in ocultos:
            MedioPago.objects.create(codigo=c, nombre=c, visible_al_cobrar=False,
                                     genera_boleta=False)
        from django.core.cache import cache
        cache.clear()

    def test_no_ofrece_las_cuentas_personales_ocultas(self):
        # Las que Jorge ocultó en agosto no deben salir en el celular.
        self._sembrar(visibles=['efectivo', 'mercadopagoaremko'],
                      ocultos=['machjorge', 'bcialda', 'copecalda'])
        codigos = self._codigos_del_selector()
        for oculto in ('machjorge', 'bcialda', 'copecalda'):
            self.assertNotIn(oculto, codigos)

    def test_si_ofrece_los_visibles(self):
        self._sembrar(visibles=['efectivo', 'mercadopagoaremko'],
                      ocultos=['machjorge'])
        codigos = self._codigos_del_selector()
        self.assertIn('efectivo', codigos)
        self.assertIn('mercadopagoaremko', codigos)

    def test_la_transferencia_a_mercado_pago_sube_de_posicion(self):
        # El síntoma que reportó Deborah: la opción correcta estaba tan abajo
        # que se elegía la de más arriba, que no boletea.
        self._sembrar(
            visibles=['efectivo', 'mercadopagoaremko'],
            ocultos=['machjorge', 'machalda', 'bicegoalda', 'bcialda',
                     'andesalda', 'scotiabankalda', 'copecjorge', 'copecalda'])
        codigos = self._codigos_del_selector()
        posicion = codigos.index('mercadopagoaremko') + 1
        completa = [c for c, _ in METODOS_PAGO_TARJETA].index('mercadopagoaremko') + 1
        self.assertLess(posicion, completa,
                        'la opción correcta debe quedar más arriba que antes')

    def test_nunca_ofrece_giftcard_ni_descuento(self):
        # Regla anterior que no se puede perder: no son plata que entró.
        self._sembrar(visibles=['efectivo', 'giftcard', 'descuento'])
        codigos = self._codigos_del_selector()
        self.assertNotIn('giftcard', codigos)
        self.assertNotIn('descuento', codigos)


class AnteLaDudaMuestraTodo(TestCase):
    """Un selector corto de más deja a Deborah sin poder cobrar. Eso es peor
    que uno largo, así que cualquier problema al leer los medios muestra todo."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='cajera_duda', email='s2@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Beto', telefono='+56944444444')
        cls.venta = VentaReserva.objects.create(cliente=cliente)

    def setUp(self):
        self.client.force_login(self.staff)
        from django.core.cache import cache
        cache.clear()

    def test_sin_medios_sembrados_muestra_todo(self):
        MedioPago.objects.all().delete()
        from django.core.cache import cache
        cache.clear()
        r = self.client.get(reverse('ventas:tarjeta_reserva', args=[self.venta.pk]))
        codigos = [c for c, _ in r.context['metodos_pago']]
        self.assertEqual(len(codigos), len(METODOS_PAGO_TARJETA))

    def test_si_falla_la_consulta_muestra_todo(self):
        from unittest.mock import patch
        with patch('facturacion.medios.filtrar_choices_pago',
                   side_effect=RuntimeError('BD caída')):
            r = self.client.get(reverse('ventas:tarjeta_reserva', args=[self.venta.pk]))
        codigos = [c for c, _ in r.context['metodos_pago']]
        self.assertEqual(len(codigos), len(METODOS_PAGO_TARJETA))


class OcultarNoEsProhibir(TestCase):
    """Ocultar un medio quita la opción del selector, pero NO debe hacer
    rebotar un cobro que ya venía en curso con ese medio."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='cajera_ok', email='s3@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Cami', telefono='+56955555555')
        cls.venta = VentaReserva.objects.create(cliente=cliente)

    def setUp(self):
        self.client.force_login(self.staff)
        MedioPago.objects.all().delete()
        MedioPago.objects.create(codigo='efectivo', nombre='Efectivo',
                                 visible_al_cobrar=True, genera_boleta=False)
        MedioPago.objects.create(codigo='machjorge', nombre='mach jorge',
                                 visible_al_cobrar=False, genera_boleta=False)
        from django.core.cache import cache
        cache.clear()

    def test_el_servidor_acepta_un_medio_oculto(self):
        # Alguien con la pantalla abierta desde antes del cambio.
        r = self.client.post(
            reverse('ventas:tarjeta_agregar_pago', args=[self.venta.pk]),
            {'monto': '15000', 'metodo_pago': 'machjorge'})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])

    def test_pero_no_acepta_uno_inventado(self):
        r = self.client.post(
            reverse('ventas:tarjeta_agregar_pago', args=[self.venta.pk]),
            {'monto': '15000', 'metodo_pago': 'no_existe'})
        self.assertEqual(r.status_code, 400)
