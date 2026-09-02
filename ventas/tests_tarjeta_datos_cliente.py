"""La tarjeta móvil completa los datos del cliente que faltan.

Pedido de Jorge (2026-09-01): la reserva se crea con lo mínimo —nombre y
teléfono, porque al teléfono hay que atender rápido— y después, cuando ya se
tienen los datos completos, hay que poder ingresarlos sin abrir el admin:
correo, RUT y comuna.

La ubicación se guarda como COMUNA, igual que en el admin: el campo `ciudad`
es texto libre y el propio modelo lo desaconseja.

Ejecutar:
    python manage.py test ventas.tests_tarjeta_datos_cliente
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ventas.models import Cliente, Comuna, Region, VentaReserva


class DatosDelClienteDesdeLaTarjeta(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='tarjeta_datos', email='s@test.cl', password='x')
        cls.region = Region.objects.create(nombre='Los Lagos', codigo='10')
        cls.otra_region = Region.objects.create(nombre='Metropolitana', codigo='13')
        cls.pv = Comuna.objects.create(nombre='Puerto Varas', region=cls.region,
                                       codigo='10301')
        cls.stgo = Comuna.objects.create(nombre='Santiago', region=cls.otra_region,
                                         codigo='13101')
        cls.cliente = Cliente.objects.create(nombre='Betty Soto',
                                             telefono='+56911111111')
        cls.venta = VentaReserva.objects.create(cliente=cls.cliente)

    def setUp(self):
        self.client.force_login(self.staff)
        self.url = reverse('ventas:tarjeta_editar_datos', args=[self.venta.pk])

    def _guardar(self, **extra):
        datos = {'comentarios': '', 'numero_documento_fiscal': ''}
        datos.update(extra)
        return self.client.post(self.url, datos)

    def test_guarda_correo_rut_y_comuna_en_el_cliente(self):
        r = self._guardar(email='betty@correo.cl',
                          documento_identidad='12.345.678-9',
                          comuna=str(self.pv.pk))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.email, 'betty@correo.cl')
        self.assertEqual(self.cliente.documento_identidad, '12.345.678-9')
        self.assertEqual(self.cliente.comuna, self.pv)

    def test_la_region_se_deriva_de_la_comuna(self):
        # Dejarlas sueltas permite el par imposible: comuna de Los Lagos con
        # región Metropolitana.
        self._guardar(comuna=str(self.stgo.pk))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.region, self.otra_region)

    def test_un_correo_mal_escrito_se_rechaza_y_no_guarda_nada(self):
        # Un correo malo no avisa: la confirmación simplemente no llega.
        r = self._guardar(email='betty@@correo', documento_identidad='999')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()['ok'])
        self.cliente.refresh_from_db()
        self.assertIsNone(self.cliente.email)
        self.assertIsNone(self.cliente.documento_identidad)

    def test_no_toca_el_telefono_ni_el_nombre(self):
        # El endpoint guarda con update_fields justamente para esto.
        self._guardar(email='betty@correo.cl', comuna=str(self.pv.pk))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.telefono, '+56911111111')
        self.assertEqual(self.cliente.nombre, 'Betty Soto')

    def test_sigue_guardando_lo_de_la_reserva(self):
        self._guardar(comentarios='Llega tarde', numero_documento_fiscal='B-77')
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.comentarios, 'Llega tarde')
        self.assertEqual(self.venta.numero_documento_fiscal, 'B-77')

    def test_dejar_la_comuna_vacia_la_borra(self):
        self.cliente.comuna = self.pv
        self.cliente.region = self.region
        self.cliente.save()
        self._guardar(comuna='')
        self.cliente.refresh_from_db()
        self.assertIsNone(self.cliente.comuna)
        self.assertIsNone(self.cliente.region)

    def test_una_comuna_inventada_no_pasa(self):
        r = self._guardar(comuna='999999')
        self.assertEqual(r.status_code, 400)

    def test_la_tarjeta_muestra_los_campos_y_los_accesos_rapidos(self):
        html = self.client.get(
            reverse('ventas:tarjeta_reserva', args=[self.venta.pk])).content.decode()
        self.assertIn('name="email"', html)
        self.assertIn('name="documento_identidad"', html)
        self.assertIn('name="comuna"', html)
        self.assertIn('Puerto Varas', html)      # acceso rápido
