"""Las condiciones para anular o cambiar, a la vista en la cotización y en el Pase.

Jorge, 26-09-2026: en la reserva #6911 la clienta pagó, anuló el mismo día y nunca había
visto las condiciones: ni la cotización ni el Pase las mostraban, y el resumen de reserva
no se le envió. Se muestran los mismos textos del resumen de reserva (admin →
Configuración Resumen), así hay un solo lugar donde editarlos.

Ejecutar:
    python manage.py test ventas.tests_condiciones_cancelacion
"""
from __future__ import annotations

import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.models import ConfiguracionResumen
from ventas.tests_pase_late_checkout import _Base
from ventas.views.ficha_reserva_view import _politicas_cancelacion, token_para_cotizacion
from whatsapp_agent.models import PropuestaReserva

ALOJAMIENTO = 'Alojamiento: con aviso de más de 48 hrs, reembolso total. Con menos, se pierde.'
TINAS = 'Tina / Masajes: con aviso de más de 24 hrs, reembolso total. Con menos, se pierde.'
TITULO = 'Condiciones para anular o cambiar'


def _configurar():
    config = ConfiguracionResumen.get_solo()
    config.politica_alojamiento = ALOJAMIENTO
    config.politica_tinas_masajes = TINAS
    config.save()


class LasCondicionesSegunLosServicios(_Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        _configurar()

    def test_cada_servicio_trae_la_suya(self):
        self.assertEqual(_politicas_cancelacion(['tina']), [TINAS])
        self.assertEqual(_politicas_cancelacion(['masaje']), [TINAS])
        self.assertEqual(_politicas_cancelacion(['cabana']), [ALOJAMIENTO])
        self.assertEqual(_politicas_cancelacion(['cabana', 'tina', 'masaje']), [ALOJAMIENTO, TINAS])

    def test_un_cargo_suelto_no_trae_ninguna(self):
        # «Hora Adicional Cabaña» se nombra como «otro»: no es una noche.
        self.assertEqual(_politicas_cancelacion(['otro']), [])
        self.assertEqual(_politicas_cancelacion([]), [])


class LaCotizacionLasMuestraAntesDeAprobar(_Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        _configurar()

    def _cotizacion(self, servicios, nombre):
        p = PropuestaReserva.objects.create(
            propuesta_id=f'p-{nombre}', idempotency_key=f'k-{nombre}', canal='whatsapp',
            external_id='+56911111111',
            payload={'cliente': {'nombre': 'Ana Soto', 'email': 'a@correo.cl',
                                 'documento_identidad': '12.345.678-5'},
                     'servicios': servicios, 'origen': 'cajon'},
            cliente_data={}, servicios=servicios, total=100000, estado='pendiente',
            expires_at=timezone.now() + datetime.timedelta(days=2))
        url = reverse('ventas:cotizacion_cliente',
                      kwargs={'token': token_para_cotizacion(p.propuesta_id)})
        return self.client.get(url).content.decode()

    def _linea(self, servicio, hora):
        return {'servicio_id': servicio.id, 'fecha': str(self.hoy), 'hora': hora,
                'cantidad_personas': 2}

    def test_noche_con_tina(self):
        html = self._cotizacion([self._linea(self.torre, '16:00'),
                                 self._linea(self.tina, '21:30')], 'noche')
        self.assertIn(TITULO, html)
        self.assertIn(ALOJAMIENTO, html)
        self.assertIn(TINAS, html)
        self.assertLess(html.index(TITULO), html.index('Aprobar cotización'))
        self.assertIn('aceptas las condiciones para anular o cambiar', html)

    def test_solo_la_que_corresponde(self):
        html = self._cotizacion([self._linea(self.tina, '19:00')], 'tina')
        self.assertIn(TINAS, html)
        self.assertNotIn(ALOJAMIENTO, html)

    def test_sin_servicios_no_hay_condiciones(self):
        html = self._cotizacion([], 'vacia')
        self.assertNotIn(TITULO, html)
        self.assertNotIn('aceptas las condiciones', html)


class ElPaseTambien(_Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        _configurar()

    def test_el_pase_de_una_noche_con_tina(self):
        v = self._venta((self.torre, self.hoy, '16:00'), (self.tina, self.hoy, '21:30'))
        r = self._pase(v)
        self.assertEqual(r.context['politicas_cancelacion'], [ALOJAMIENTO, TINAS])
        self.assertContains(r, TITULO)
        self.assertContains(r, 'Por si necesitas anular o cambiar tu reserva')


UNICA = ('Si nos avisas con 48 horas o más de anticipación, te devolvemos el 100% o cambiamos la '
         'fecha sin costo. Con menos de 48 horas, la reserva se pierde.')


class UnaSolaReglaParaLosTres(_Base):
    """Jorge, 26-09-2026: 48 horas para tinas, masajes y cabañas. Con el mismo texto en los
    dos campos del admin, una noche con tina lo muestra una sola vez."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        config = ConfiguracionResumen.get_solo()
        config.politica_alojamiento = UNICA
        config.politica_tinas_masajes = UNICA
        config.save()

    def test_la_cotizacion_y_el_pase_la_muestran_una_vez(self):
        self.assertEqual(_politicas_cancelacion(['cabana', 'tina', 'masaje']), [UNICA])
        v = self._venta((self.torre, self.hoy, '16:00'), (self.tina, self.hoy, '21:30'))
        self.assertEqual(self._pase(v).content.decode().count(UNICA), 1)

    def test_el_resumen_de_reserva_tambien(self):
        from ventas.views.resumen_reserva_view import _generar_texto_resumen
        v = self._venta((self.torre, self.hoy, '16:00'), (self.tina, self.hoy, '21:30'))
        texto = _generar_texto_resumen(v, ConfiguracionResumen.get_solo())
        self.assertEqual(texto.count(UNICA), 1)
