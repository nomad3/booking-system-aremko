"""La carta de la giftcard dice lo que se compró encima de la experiencia.

Jorge (07-09-2026): un cliente compra una Pausa junto al Río ($110.000) y
quiere sumarle una ambientación romántica ($32.000), "y el problema es que en
la giftcard no aparece la ambientación". Lo mismo con una tabla de quesos.

Deborah ya lo anotaba en `detalle_especial` ("Incluye: 1 Tabla Jamón", 4
casos reales) pero la carta no lo imprimía: el regalado nunca se enteraba de
lo que le habían comprado. El monto ya lo cubría; faltaba decirlo.

Ejecutar:
    python manage.py test ventas.tests_giftcard_agregados
"""
from __future__ import annotations

import datetime

from django.test import TestCase

from ventas.models import GiftCard
from ventas.services.giftcard_pdf_service import GiftCardPDFService


def _gc(detalle=''):
    hoy = datetime.date.today()
    return GiftCard.objects.create(
        monto_inicial=142000, monto_disponible=142000,
        fecha_emision=hoy, fecha_vencimiento=hoy + datetime.timedelta(days=365),
        estado='por_cobrar', destinatario_nombre='Camila',
        mensaje_personalizado='Para ti', servicio_asociado='pausa_rio',
        detalle_especial=detalle)


class LaCartaImprimeLosAgregados(TestCase):
    def test_el_contexto_lleva_los_agregados(self):
        datos = GiftCardPDFService.datos_carta(_gc('Ambientación romántica Clásica'))
        self.assertEqual(datos['agregados'], 'Ambientación romántica Clásica')

    def test_la_carta_movil_lo_dice(self):
        # Es el formato que se manda de verdad (todo llama con formato='mobile').
        datos = GiftCardPDFService.datos_carta(_gc('Ambientación romántica Clásica'))
        html = GiftCardPDFService.generar_html_giftcard_mobile(datos)
        self.assertIn('Incluye además', html)
        self.assertIn('Ambientación romántica Clásica', html)

    def test_la_carta_clasica_tambien(self):
        datos = GiftCardPDFService.datos_carta(_gc('Tabla de quesos'))
        html = GiftCardPDFService.generar_html_giftcard(datos)
        self.assertIn('INCLUYE ADEMÁS', html)
        self.assertIn('Tabla de quesos', html)

    def test_sin_agregados_no_aparece_la_etiqueta(self):
        # Las 479 giftcards sin extras no pueden salir con un "Incluye además"
        # vacío.
        datos = GiftCardPDFService.datos_carta(_gc(''))
        html = GiftCardPDFService.generar_html_giftcard_mobile(datos)
        self.assertNotIn('Incluye además', html)

    def test_solo_espacios_cuenta_como_nada(self):
        datos = GiftCardPDFService.datos_carta(_gc('   \n '))
        self.assertEqual(datos['agregados'], '')
        self.assertNotIn('Incluye además',
                         GiftCardPDFService.generar_html_giftcard_mobile(datos))

    def test_en_la_carta_oscura_el_texto_va_en_blanco(self):
        # La carta móvil es verde oscuro. La primera versión heredó el gris
        # oscuro del brochure y "Incluye además" quedó invisible.
        datos = GiftCardPDFService.datos_carta(_gc('Tabla de quesos'))
        html = GiftCardPDFService.generar_html_giftcard_mobile(datos)
        i = html.index('.exp-extra {')
        regla = html[i:html.index('}', i)]
        self.assertIn('color: #ffffff', regla)
        self.assertNotIn('#3F3A33', regla)

    def test_un_menor_que_no_rompe_el_pdf(self):
        # Texto libre del admin: un "<" suelto reventaría el HTML/PDF.
        datos = GiftCardPDFService.datos_carta(_gc('Tabla <premium> & jugo'))
        html = GiftCardPDFService.generar_html_giftcard_mobile(datos)
        self.assertIn('Tabla &lt;premium&gt; &amp; jugo', html)
        self.assertNotIn('<premium>', html)
