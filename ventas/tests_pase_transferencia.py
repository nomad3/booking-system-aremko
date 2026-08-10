"""El Pase ofrece TRANSFERENCIA primero y la tarjeta como segunda opción.

Decisión de Jorge (2026-08-10) después de medir junio contra julio: por
transferencia Mercado Pago no cobra comisión y por tarjeta cobra ~3,1%. El
link de pago no se elimina —quien quiera pagar de noche con tarjeta debe
poder hacerlo, porque WhatsApp todavía lo contesta una persona— pero deja de
ser lo primero que se ve.
"""
from django.db.models.signals import post_save
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from control_gestion.signals import react_to_reserva_change

from .models import Cliente, ConfiguracionResumen, VentaReserva
from .signals.main_signals import actualizar_tramo_y_premios_on_pago
from .views.ficha_reserva_view import token_para_reserva

# Mismo motivo que tests_ficha_reserva_aviso_pago: estas señales piden tablas
# del drift AR-033/034 que la BD de test no tiene.
_SENSORES = (actualizar_tramo_y_premios_on_pago, react_to_reserva_change)


class PaseTransferenciaPrimeroTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for receptor in _SENSORES:
            post_save.disconnect(receptor, sender=VentaReserva)

    @classmethod
    def tearDownClass(cls):
        for receptor in _SENSORES:
            post_save.connect(receptor, sender=VentaReserva)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            nombre='Pedro Rojas', telefono='+56911113333')
        config = ConfiguracionResumen.get_solo()
        config.nombre_beneficiario = 'Aremko Hotel Spa SpA'
        config.numero_cuenta_transferencia = '1234567890'
        config.correo_confirmacion_pago = 'pagos@aremko.cl'
        config.save()

    def _pase(self, saldo=60000):
        venta = VentaReserva.objects.create(
            cliente=self.cliente, total=saldo, saldo_pendiente=saldo,
            estado_pago='pendiente', fecha_reserva=timezone.now())
        return self.client.get(reverse(
            'ventas:ficha_reserva_cliente',
            kwargs={'token': token_para_reserva(venta.id)}))

    def test_el_bloque_principal_es_la_transferencia(self):
        r = self._pase()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Datos de Transferencia')
        self.assertContains(r, 'pago-principal')
        # Los datos de la cuenta salen de la configuración, no del código.
        self.assertContains(r, 'Aremko Hotel Spa SpA')
        self.assertContains(r, '1234567890')

    def test_las_cuotas_se_piden_por_whatsapp(self):
        r = self._pase()
        self.assertContains(r, '12 cuotas')
        self.assertContains(r, 'wa.me')

    def test_la_tarjeta_sigue_disponible_como_segunda_opcion(self):
        """Opción B: nadie queda sin poder pagar a las 11 de la noche."""
        r = self._pase()
        self.assertContains(r, 'link-tarjeta')
        self.assertContains(r, 'paga con tarjeta ahora')
        # Y ya no está el botón grande que encabezaba la ficha.
        self.assertNotContains(r, 'Pagar online — hasta 12 cuotas')

    def test_sin_saldo_no_se_ofrece_pagar(self):
        r = self._pase(saldo=0)
        self.assertNotContains(r, 'Datos de Transferencia')
