"""Las boletas de la visita viven en El Pase del cliente.

Idea de Jorge (04-09-2026): «se podría agregar las boletas en El Pase del
cliente... otra manera de darle valor al Pase». Mejor que una página nueva —
el cliente ya tiene ese enlace guardado desde que reservó, se actualiza solo
cuando se emite otra boleta, y no hay que enseñarle una dirección más.

Su ejemplo, que es el caso a cubrir: el cliente transfiere (una boleta), al
llegar compra un café y lo paga en efectivo (otra), y al irse otro café
(otra). Esa reserva tiene tres boletas y las tres tienen que estar ahí.

La regla que no se puede romper: solo boletas REALES. El Pase se abre sin
clave; mostrar ahí una de certificación o simulada sería entregarle al
cliente un documento sin valor tributario presentado como si lo tuviera.

Ejecutar:
    python manage.py test ventas.tests_pase_boletas
"""
from __future__ import annotations

from django.test import TestCase

from facturacion.models import BoletaElectronica
from ventas.models import Cliente, Pago, VentaReserva


def _boleta(venta, folio, monto=10000, ambiente='produccion', estado='aceptada',
            glosa='Servicios Aremko'):
    return BoletaElectronica.objects.create(
        pago=None, venta_reserva=venta, tipo_dte=39, ambiente=ambiente,
        folio=folio, estado=estado, glosa=glosa,
        monto_total=monto, monto_neto=int(monto / 1.19),
        monto_iva=monto - int(monto / 1.19))


class LasBoletasEnElPase(TestCase):
    def setUp(self):
        cliente = Cliente.objects.create(nombre='Elena', telefono='+56911223344')
        self.venta = VentaReserva.objects.create(cliente=cliente)

    def _pase(self):
        from ventas.views.ficha_reserva_view import token_para_reserva
        return self.client.get(
            f'/ventas/reserva/{token_para_reserva(self.venta.id)}/')

    def test_el_caso_de_jorge_tres_boletas(self):
        # Transferencia + café + café: las tres tienen que aparecer.
        _boleta(self.venta, 100, 60000, glosa='Reserva')
        _boleta(self.venta, 101, 2500, glosa='Cafe')
        _boleta(self.venta, 102, 2500, glosa='Cafe')
        html = self._pase().content.decode()
        for folio in ('N° 100', 'N° 101', 'N° 102'):
            self.assertIn(folio, html)

    def test_muestra_el_monto_a_la_chilena(self):
        _boleta(self.venta, 103, 1087500)
        self.assertIn('$1.087.500', self._pase().content.decode())

    def test_lleva_al_enlace_de_cada_boleta(self):
        b = _boleta(self.venta, 104)
        html = self._pase().content.decode()
        self.assertIn(f'/boletas/b/{b.token_consulta}/', html)

    def test_sin_boletas_no_muestra_la_seccion(self):
        # Un bloque vacío preguntando por boletas inexistentes genera dudas.
        self.assertNotIn('boleta electrónica', self._pase().content.decode().lower())

    def test_una_boleta_de_certificacion_no_se_le_muestra_al_cliente(self):
        _boleta(self.venta, 105, ambiente='certificacion')
        html = self._pase().content.decode()
        self.assertNotIn('N° 105', html)

    def test_una_simulada_tampoco(self):
        _boleta(self.venta, 106, estado='simulada')
        self.assertNotIn('N° 106', self._pase().content.decode())

    def test_una_en_error_tampoco(self):
        # No existe ante el SII: mostrarla prometería algo que no hay.
        _boleta(self.venta, 107, estado='error')
        self.assertNotIn('N° 107', self._pase().content.decode())

    def test_no_muestra_boletas_de_otra_reserva(self):
        otra = VentaReserva.objects.create(
            cliente=Cliente.objects.create(nombre='Otro', telefono='+56955443322'))
        _boleta(otra, 108)
        self.assertNotIn('N° 108', self._pase().content.decode())

    def test_las_ordena_por_folio(self):
        _boleta(self.venta, 111, glosa='tercera')
        _boleta(self.venta, 109, glosa='primera')
        _boleta(self.venta, 110, glosa='segunda')
        html = self._pase().content.decode()
        self.assertLess(html.index('N° 109'), html.index('N° 110'))
        self.assertLess(html.index('N° 110'), html.index('N° 111'))

    def test_un_problema_con_las_boletas_no_tumba_el_pase(self):
        # El Pase es lo que el cliente muestra al llegar: tiene que abrir
        # aunque la parte de boletas falle.
        from unittest.mock import patch
        _boleta(self.venta, 112)
        with patch('facturacion.models.BoletaElectronica.objects') as m:
            m.filter.side_effect = RuntimeError('BD caída')
            r = self._pase()
        self.assertEqual(r.status_code, 200)
