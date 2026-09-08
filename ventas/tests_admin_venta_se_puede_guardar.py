"""La página de la venta dibuja sus campos y se puede guardar.

08-09-2026, Deborah: "no puedo modificar reserva, me indica error". El aviso
rojo salía sin ningún error visible. Causa: el 07-09 se agregó a
VentaReservaAdmin un SEGUNDO método `render_change_form` (para el botón de
empaquetar giftcards). Python se queda con la última definición, así que el
original —que pone `fieldsets_bajo_pagos` y `pos_ancla_pagos` en el
contexto— quedó pisado. Sin esas variables la plantilla no dibuja ningún
fieldset: desapareció el bloque con cliente y estado, el formulario los
seguía exigiendo, y ningún guardado podía pasar. Para todos los usuarios,
desde las 18:00 del 07-09.

Estas pruebas miran la PÁGINA, no el cambio: que los campos estén, que un
guardado sin cambios pase, y que la clase defina el método una sola vez.

Ejecutar:
    python manage.py test ventas.tests_admin_venta_se_puede_guardar
"""
from __future__ import annotations

import inspect
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ventas.models import Cliente, VentaReserva


class LaPaginaDeLaVenta(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.jefe = get_user_model().objects.create_superuser(
            username='jorge_t', email='j@test.cl', password='x')
        cls.cliente = Cliente.objects.create(nombre='Nicolás', telefono='+56968044230')
        cls.venta = VentaReserva.objects.create(cliente=cls.cliente)

    def setUp(self):
        self.client.force_login(self.jefe)
        self.url = reverse('admin:ventas_ventareserva_change', args=[self.venta.pk])

    def test_dibuja_el_bloque_de_cliente_y_estado(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn('field-cliente', html)
        self.assertIn('field-estado_reserva', html)
        self.assertIn('name="estado_reserva"', html)

    def test_un_guardado_sin_cambios_pasa(self):
        # Lo mínimo que un formulario tiene que poder hacer.
        page = self.client.get(self.url).content.decode()
        data = {}
        for m in re.finditer(r'<input[^>]+name="([^"]+)"[^>]*>', page):
            tag = m.group(0)
            if re.search(r'type="(submit|button|file|checkbox)"', tag):
                continue
            v = re.search(r'value="([^"]*)"', tag)
            data[m.group(1)] = v.group(1) if v else ''
        for m in re.finditer(r'<select[^>]*\bname="([^"]+)"[^>]*>(.*?)</select>', page, re.S):
            sel = re.search(r'<option[^>]*\bselected\b[^>]*value="([^"]*)"|'
                            r'<option[^>]*value="([^"]*)"[^>]*\bselected\b', m.group(2))
            data[m.group(1)] = (sel.group(1) or sel.group(2)) if sel else ''
        for m in re.finditer(r'<textarea[^>]+name="([^"]+)"[^>]*>(.*?)</textarea>', page, re.S):
            data[m.group(1)] = m.group(2)
        data['_continue'] = '1'
        r = self.client.post(self.url, data)
        self.assertEqual(r.status_code, 302,
                         'el guardado volvió con errores: ' +
                         ' '.join(re.findall(r'errorlist[^<]*<li>([^<]+)', r.content.decode())))

    def test_render_change_form_esta_definido_una_sola_vez(self):
        # El bug fue exactamente esto: dos `def render_change_form` en la misma
        # clase. Python no avisa; se queda con el último.
        from ventas.admin import VentaReservaAdmin
        fuente = inspect.getsource(VentaReservaAdmin)
        self.assertEqual(fuente.count('def render_change_form('), 1)
