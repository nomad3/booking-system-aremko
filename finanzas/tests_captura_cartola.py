# -*- coding: utf-8 -*-
"""Capturas del celular → líneas para pegar (Jorge, 2026-08-12).

«Para subir archivos de mi cuenta rut a finanzas lo subíamos con capturas de
pantalla de mi celular. Estoy intentando subir una captura y no me deja.»

Nunca se pudo: el cargador de cartolas conoce cuatro formatos por sus bytes y
ninguno es una imagen. Las capturas pasaban por el chat, donde yo las leía.
Esto mete ese trabajo adentro del sistema, con una regla que no se negocia:
la captura NO escribe movimientos, llena el cuadro de texto que ya se pega a
mano. El error que más importa evitar no es que invente un movimiento —es que
lea mal un monto—, y el texto es donde eso se caza antes de ser plata.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from finanzas.models import MovimientoFinanciero
from finanzas.vision import limpiar_salida, validar_capturas


def _imagen(nombre='captura.png', tam=1000):
    return SimpleUploadedFile(nombre, b'\x89PNG' + b'0' * tam, 'image/png')


class LimpiarSalidaTest(TestCase):
    """Lo que el modelo devuelve no se pega tal cual: se filtra."""

    def test_deja_solo_las_lineas_con_forma_de_movimiento(self):
        crudo = ('Aquí están los movimientos:\n'
                 '```\n'
                 '04-08-2026 ; Pago Twilio Sendgrid ; -22316\n'
                 '03-08-2026 ; Tef De Aremko Hotel Spa ; 588136\n'
                 '```\n'
                 'Espero que te sirva.')
        texto, dudosas = limpiar_salida(crudo)
        self.assertEqual(texto,
                         '04-08-2026 ; Pago Twilio Sendgrid ; -22316\n'
                         '03-08-2026 ; Tef De Aremko Hotel Spa ; 588136')
        self.assertEqual(dudosas, [])

    def test_las_dudosas_salen_aparte_y_no_se_pegan(self):
        """Preferimos que falte un movimiento a que entre uno mal."""
        texto, dudosas = limpiar_salida(
            '04-08-2026 ; Pago Render.com ; -119443\n'
            '# dudosa: línea cortada el 05-08, monto ilegible\n')
        self.assertEqual(texto, '04-08-2026 ; Pago Render.com ; -119443')
        self.assertEqual(dudosas, ['línea cortada el 05-08, monto ilegible'])

    def test_descarta_lo_que_no_calza_con_el_formato(self):
        """Saldos, encabezados y montos con puntos NO pasan: el parser de
        abajo los rechazaría igual, pero acá ni siquiera llegan."""
        texto, _ = limpiar_salida(
            'Saldo Contable ; $211.408\n'
            '04-08-2026 ; Comision Transaccion Internacional ; -473\n'
            'Movimientos\n'
            '4 de agosto de 2026\n')
        self.assertEqual(texto,
                         '04-08-2026 ; Comision Transaccion Internacional ; -473')

    def test_sin_movimientos_devuelve_vacio(self):
        self.assertEqual(limpiar_salida('No encontré nada.'), ('', []))
        self.assertEqual(limpiar_salida(''), ('', []))
        self.assertEqual(limpiar_salida(None), ('', []))


class ValidarCapturasTest(TestCase):
    """Se rechaza antes de gastar una llamada al modelo."""

    def test_acepta_una_captura_normal(self):
        self.assertEqual(validar_capturas([_imagen()]), (True, ''))

    def test_sin_archivos(self):
        ok, error = validar_capturas([])
        self.assertFalse(ok)
        self.assertIn('ninguna captura', error)

    def test_un_pdf_no_es_captura(self):
        ok, error = validar_capturas([_imagen('cartola.pdf')])
        self.assertFalse(ok)
        self.assertIn('no parece una imagen', error)

    def test_demasiadas_de_una_vez(self):
        ok, error = validar_capturas([_imagen(f'c{i}.png') for i in range(9)])
        self.assertFalse(ok)
        self.assertIn('dos tandas', error)

    def test_una_imagen_gigante(self):
        ok, error = validar_capturas([_imagen('grande.png', 9 * 1024 * 1024)])
        self.assertFalse(ok)
        self.assertIn('tope', error)


class SubirCapturaEnLaVistaTest(TestCase):
    """El circuito completo, con el modelo mockeado."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            'jorge_test', 'j@test.cl', 'clave-larga-de-prueba')
        self.client.force_login(self.user)
        self.url = reverse('finanzas:cargar_movimientos')

    @mock.patch('finanzas.vision.leer_capturas')
    def test_la_captura_llena_el_cuadro_y_NO_escribe_nada(self, m_leer):
        m_leer.return_value = (
            '04-08-2026 ; Pago Twilio Sendgrid ; -22316\n'
            '04-08-2026 ; Comision Transaccion Internacional ; -473', [], '')
        r = self.client.post(self.url, {'capturas': _imagen()})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Pago Twilio Sendgrid')
        self.assertContains(r, 'Leí')
        # Lo que de verdad importa: la contabilidad sigue intacta.
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

    @mock.patch('finanzas.vision.leer_capturas')
    def test_las_dudosas_se_muestran_para_que_las_agregue_a_mano(self, m_leer):
        m_leer.return_value = ('04-08-2026 ; Pago Render.com ; -119443',
                               ['05-08, monto cortado'], '')
        r = self.client.post(self.url, {'capturas': _imagen()})
        self.assertContains(r, '05-08, monto cortado')
        self.assertContains(r, 'las dejé fuera')

    @mock.patch('finanzas.vision.leer_capturas')
    def test_si_el_modelo_falla_lo_dice_sin_romper_la_pagina(self, m_leer):
        m_leer.return_value = ('', [], 'No pude leer la captura.')
        r = self.client.post(self.url, {'capturas': _imagen()})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'No pude leer la captura.')

    def test_un_archivo_que_no_es_imagen_se_rechaza_sin_llamar_al_modelo(self):
        with mock.patch('finanzas.vision.leer_capturas') as m_leer:
            r = self.client.post(self.url, {'capturas': _imagen('cartola.pdf')})
        m_leer.assert_not_called()
        self.assertContains(r, 'no parece una imagen')

    def test_el_pegado_a_mano_sigue_funcionando_igual(self):
        """La captura es un camino nuevo, no un reemplazo."""
        r = self.client.post(self.url, {
            'texto': '04-08-2026 ; Pago Twilio Sendgrid ; -22316',
            'cuenta': 'cuentarut_jorge'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(MovimientoFinanciero.objects.count(), 0,
                         'La propuesta no escribe: eso lo hace la confirmación')


class CapturaEnLaPaginaDeCartolasTest(TestCase):
    """Jorge sube la captura en «Cargar cartola bancaria» —la página con el
    nombre obvio— y le decía «no reconozco el archivo». El lector estaba en la
    otra página. Ahora la de cartolas la acepta, la lee y lo manda a revisar.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            'jorge_cartola', 'j2@test.cl', 'clave-larga-de-prueba')
        self.client.force_login(self.user)
        self.url = reverse('finanzas:cargar_cartola')

    @mock.patch('finanzas.vision.leer_capturas')
    def test_una_captura_en_cartolas_lleva_a_revisar_con_el_texto_puesto(self, m_leer):
        m_leer.return_value = ('04-08-2026 ; Pago Twilio Sendgrid ; -22316', [], '')
        r = self.client.post(self.url, {'archivo': _imagen()})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], reverse('finanzas:cargar_movimientos'))

        # Y al llegar, el texto ya está en el cuadro.
        destino = self.client.get(r['Location'])
        self.assertContains(destino, 'Pago Twilio Sendgrid')
        self.assertContains(destino, 'Leí')
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

    @mock.patch('finanzas.vision.leer_capturas')
    def test_el_texto_no_se_repite_al_recargar(self, m_leer):
        """Se saca de la sesión al mostrarlo: un F5 no lo trae de nuevo."""
        m_leer.return_value = ('04-08-2026 ; Pago Render.com ; -119443', [], '')
        self.client.post(self.url, {'archivo': _imagen()})
        primera = self.client.get(reverse('finanzas:cargar_movimientos'))
        self.assertContains(primera, 'Pago Render.com')
        segunda = self.client.get(reverse('finanzas:cargar_movimientos'))
        self.assertNotContains(segunda, 'Pago Render.com')

    @mock.patch('finanzas.vision.leer_capturas')
    def test_si_no_se_puede_leer_se_queda_en_cartolas_con_el_motivo(self, m_leer):
        m_leer.return_value = ('', [], 'No encontré movimientos en la captura.')
        r = self.client.post(self.url, {'archivo': _imagen()})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'No encontré movimientos')

    def test_los_formatos_de_siempre_siguen_su_camino(self):
        """La captura es una rama nueva, no toca las otras cuatro."""
        from finanzas.views import _es_imagen
        self.assertFalse(_es_imagen(b'PK\x03\x04'))          # xlsx
        self.assertFalse(_es_imagen(b'\xd0\xcf\x11\xe0'))    # xls
        self.assertFalse(_es_imagen(b'%PDF-1.4'))            # pdf
        self.assertFalse(_es_imagen(b';TIPO;FECHA'))         # BSA.dat

    def test_reconoce_los_formatos_de_captura(self):
        from finanzas.views import _es_imagen
        self.assertTrue(_es_imagen(b'\x89PNG\r\n\x1a\n'))              # PNG
        self.assertTrue(_es_imagen(b'\xff\xd8\xff\xe0' + b'0' * 8))    # JPEG
        self.assertTrue(_es_imagen(b'RIFF' + b'0000' + b'WEBP'))       # WEBP
        self.assertTrue(_es_imagen(b'0000ftypheic'))                   # HEIC
