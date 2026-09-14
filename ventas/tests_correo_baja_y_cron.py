"""Deploy 1 de H-111: la baja se lee de corrido y el cron manda un lote por pasada.

Jorge (12-09-2026): «que esté establecida claramente la posibilidad de
desinscribirse de la lista de correos». El enlace existía, pero decía «Darse de
baja» en letra chica al final de un pie gris. Ahora es una frase completa con el
enlace adentro, y la versión de texto plano la lleva igual.

El cron de campañas pega cada 5 minutos (cron-job.org) y lanzaba un envío
COMPLETO cada vez, con procesos que dormían entre lote y lote y se apilaban
sobre la misma campaña. Ahora cada pasada manda un lote y termina.

Ejecutar:
    python manage.py test ventas.tests_correo_baja_y_cron
"""
from __future__ import annotations

import os
import re
from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from ventas.models import Cliente, EmailCampaign, EmailRecipient
from ventas.utils.email_footer import get_email_footer_html, get_email_footer_text

CORREO = 'ana.prueba@test.cl'
URL_BAJA = f'https://www.aremko.cl/unsubscribe/{CORREO}/'


class LaBajaSeLee(TestCase):
    def test_el_pie_html_lleva_la_frase_completa_con_el_enlace_adentro(self):
        html = get_email_footer_html(CORREO)
        self.assertIn('Si no quieres recibir m&aacute;s correos de Aremko', html)
        # El enlace envuelve la acción, no una palabra suelta al final.
        self.assertRegex(
            html,
            r'<a href="' + re.escape(URL_BAJA) + r'"[^>]*>date de baja aqu&iacute; con un clic</a>')

    def test_el_pie_de_texto_plano_tambien(self):
        txt = get_email_footer_text(CORREO)
        self.assertIn(f'date de baja aquí con un clic: {URL_BAJA}', txt)

    def test_ya_no_queda_el_texto_chico_de_antes(self):
        self.assertNotIn('>Darse de baja<', get_email_footer_html(CORREO))

    def test_el_correo_que_sale_de_verdad_lleva_la_frase_y_el_boton_de_gmail(self):
        # Verificar la página, no el cambio: lo que importa es lo que SALE por el
        # motor, no la función del pie por separado.
        from ventas.management.commands.enviar_campana_email import Command
        cliente = Cliente.objects.create(nombre='Ana Prueba', telefono='+56911111111',
                                         email=CORREO)
        campana = EmailCampaign.objects.create(
            name='prueba pie', email_subject_template='Hola {nombre_cliente}',
            email_body_template='<p>Hola {nombre_cliente}</p>', status='ready',
            ai_variation_enabled=False,
            schedule_config={'ai_enabled': False, 'batch_size': 5, 'interval_minutes': 5})
        dest = EmailRecipient.objects.create(
            campaign=campana, client=cliente, email=CORREO, name='Ana',
            personalized_subject='Hola Ana', personalized_body='<p>Hola Ana</p>')
        cmd = Command()
        cmd.stdout = open(os.devnull, 'w')
        self.assertTrue(cmd.send_email(dest, dry_run=False))
        self.assertEqual(len(mail.outbox), 1)
        enviado = mail.outbox[0]
        html = [c for c, t in enviado.alternatives if t == 'text/html'][0]
        self.assertIn('date de baja aqu&iacute; con un clic', html)
        self.assertIn(URL_BAJA, html)
        self.assertIn(URL_BAJA, enviado.extra_headers['List-Unsubscribe'])
        self.assertEqual(enviado.extra_headers['List-Unsubscribe-Post'],
                         'List-Unsubscribe=One-Click')


class CronUnLotePorPasada(TestCase):
    def setUp(self):
        self.url = reverse('ventas:cron_enviar_campanas_email')

    def _campana_lista(self):
        return EmailCampaign.objects.create(
            name='lista', email_subject_template='a', email_body_template='b',
            status='ready')

    @patch.dict(os.environ, {'CRON_TOKEN': 'tok'})
    @patch('ventas.views.cron_views.subprocess.Popen')
    def test_lanza_el_envio_con_un_lote_por_pasada(self, popen):
        self._campana_lista()
        r = self.client.get(self.url + '?token=tok')
        self.assertEqual(r.status_code, 200)
        popen.assert_called_once()
        args = popen.call_args[0][0]
        self.assertEqual(args[:3], ['python', 'manage.py', 'enviar_campana_email'])
        self.assertIn('--auto', args)
        self.assertIn('--single-batch', args, 'sin esto se apilan procesos cada 5 min')

    @patch.dict(os.environ, {'CRON_TOKEN': 'tok'})
    @patch('ventas.views.cron_views.subprocess.Popen')
    def test_con_token_malo_no_lanza_nada(self, popen):
        self._campana_lista()
        r = self.client.get(self.url + '?token=otro')
        self.assertEqual(r.status_code, 403)
        popen.assert_not_called()

    @patch.dict(os.environ, {'CRON_TOKEN': 'tok'})
    @patch('ventas.views.cron_views.subprocess.Popen')
    def test_sin_campanas_en_cola_no_lanza_nada(self, popen):
        r = self.client.get(self.url + '?token=tok')
        self.assertEqual(r.status_code, 200)
        popen.assert_not_called()
