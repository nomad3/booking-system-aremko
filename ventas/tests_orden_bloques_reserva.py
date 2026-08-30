"""Orden de los bloques al editar una reserva (Jorge, 2026-08-30).

Al abrir una reserva lo primero que se mira es el dinero: qué se vendió, qué se
pagó, qué falta. El Pase y las dos secciones de comandas se usan DESPUÉS de que
la plata está cuadrada, y arriba del todo empujaban hacia abajo justamente lo
que se consulta primero.

Django dibuja TODOS los fieldsets antes de TODOS los inlines y no permite
intercalarlos, así que el reordenamiento se hace en la plantilla. Eso lo vuelve
frágil de una forma particular: si alguien renombra un bloque o cambia el orden
de los inlines, la página NO se cae — simplemente vuelve a quedar desordenada, y
nadie se entera hasta que lo nota mirando.

Ejecutar:
    python manage.py test ventas.tests_orden_bloques_reserva
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ventas.admin import PagoInline, VentaReservaAdmin
from ventas.models import Cliente, VentaReserva


class LoQueSeDeclaraExiste(TestCase):
    """El reordenamiento se apoya en nombres declarados a mano. Si un bloque se
    renombra y nadie actualiza la lista, la plantilla deja de reconocerlo y ese
    bloque se queda arriba, en silencio."""

    def test_los_bloques_declarados_existen_en_el_formulario(self):
        reales = {nombre for nombre, _ in VentaReservaAdmin.fieldsets}
        for declarado in VentaReservaAdmin.FIELDSETS_BAJO_PAGOS:
            self.assertIn(declarado, reales,
                          f'«{declarado}» ya no es un bloque del formulario: '
                          f'se renombró y quedaría arriba otra vez')

    def test_el_ancla_sigue_estando_entre_los_inlines(self):
        self.assertIn(PagoInline, VentaReservaAdmin.inlines)


class ElOrdenQueVeJorge(TestCase):
    """Lo único que prueba de verdad el reordenamiento es mirar el HTML: los
    dos bloques anteriores comprueban las piezas, este comprueba el resultado."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='jorge_test', email='j@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Priscila', telefono='+56926210906')
        cls.venta = VentaReserva.objects.create(cliente=cliente)

    def setUp(self):
        self.client.force_login(self.staff)
        url = reverse('admin:ventas_ventareserva_change', args=[self.venta.pk])
        self.html = self.client.get(url).content.decode()

    def _pos(self, aguja):
        i = self.html.find(aguja)
        self.assertNotEqual(i, -1, f'no encontré «{aguja}» en el formulario')
        return i

    def test_el_pase_va_despues_de_los_pagos(self):
        self.assertGreater(self._pos('El Pase del cliente'),
                           self._pos('id="pagos-group"'))

    def test_la_comanda_del_cliente_va_despues_de_los_pagos(self):
        self.assertGreater(self._pos('Comanda del Cliente'),
                           self._pos('id="pagos-group"'))

    def test_la_gestion_de_comandas_va_despues_de_los_pagos(self):
        self.assertGreater(self._pos('Gestión de Comandas'),
                           self._pos('id="pagos-group"'))

    def test_los_servicios_y_los_pagos_siguen_arriba_del_pase(self):
        """La contraparte: bajar esos tres no puede haber bajado también lo que
        se mira primero."""
        pase = self._pos('El Pase del cliente')
        self.assertLess(self._pos('id="reservaservicios-group"'), pase)
        self.assertLess(self._pos('id="pagos-group"'), pase)

    def test_los_tres_bloques_aparecen_UNA_sola_vez(self):
        """El reordenamiento dibuja los fieldsets en dos recorridos distintos.
        Un error de condición los dejaría duplicados: arriba y abajo."""
        for bloque in ('El Pase del cliente', 'Comanda del Cliente (WhatsApp)',
                       'Gestión de Comandas (Personal)'):
            self.assertEqual(self.html.count(bloque), 1,
                             f'«{bloque}» aparece {self.html.count(bloque)} veces')

    def test_las_comandas_quedan_pegadas_a_su_bloque(self):
        """«Gestión de Comandas» dice que las comandas se muestran justo abajo.
        Si el inline de comandas quedara antes, la frase mentiría."""
        self.assertLess(self._pos('Gestión de Comandas'),
                        self._pos('id="comandas-group"'))
