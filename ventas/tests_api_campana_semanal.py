"""H-111 · POST /marketing/api/campana-semanal/: Datamatic manda asunto y cuerpo,
Aremko arma el lote y deja la campaña en Borrador.

Reglas de Jorge (12-09-2026) que estas pruebas defienden: no se dispara sola,
máximo 1.000 por lote, van todos los clientes con correo en fila (última compra
más reciente primero, sin repetir a quien recibió hace menos de 4 semanas), y
la IA queda apagada aunque la pidan.

Ejecutar:
    python manage.py test ventas.tests_api_campana_semanal
"""
from __future__ import annotations

import datetime
import json

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ventas.models import (Cliente, EmailBlacklist, EmailCampaign, EmailRecipient,
                           NewsletterSubscriber, VentaReserva)

LLAVE = 'llave-de-prueba'
CUERPO = ('<table role="presentation" width="600"><tr><td>Hola {nombre_cliente}, '
          'esta semana en Aremko…</td></tr></table>')


def _cliente(nombre, email, hace_dias=None):
    """Un cliente con correo; si `hace_dias` viene, con una compra de esa fecha."""
    c = Cliente.objects.create(nombre=nombre, email=email,
                               telefono=f'+569{Cliente.objects.count() + 10000000:08d}')
    if hace_dias is not None:
        VentaReserva.objects.create(
            cliente=c, fecha_reserva=timezone.now() - datetime.timedelta(days=hace_dias))
    return c


@override_settings(AUTOMATION_API_KEY=LLAVE)
class Base(TestCase):
    def setUp(self):
        self.url = reverse('api_campana_semanal')

    def _post(self, cuerpo=None, llave=LLAVE, **extra):
        datos = {'asunto': 'Hola {nombre_cliente}', 'cuerpo_html': CUERPO}
        datos.update(cuerpo or {})
        kw = {'HTTP_X_API_KEY': llave} if llave is not None else {}
        return self.client.post(self.url, data=json.dumps(datos),
                                content_type='application/json', **kw)


class LaLlave(Base):
    def test_sin_llave_401_y_no_crea_nada(self):
        _cliente('Ana Soto', 'ana@test.cl', 3)
        r = self._post(llave=None)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(EmailCampaign.objects.count(), 0)

    def test_llave_mala_401(self):
        _cliente('Ana Soto', 'ana@test.cl', 3)
        self.assertEqual(self._post(llave='otra').status_code, 401)
        self.assertEqual(EmailCampaign.objects.count(), 0)

    def test_get_no_existe(self):
        self.assertEqual(self.client.get(self.url, HTTP_X_API_KEY=LLAVE).status_code, 405)


class LaCampanaQueSeCrea(Base):
    def test_nace_en_borrador_con_la_ia_apagada_y_lotes_de_50(self):
        _cliente('Ana Soto', 'ana@test.cl', 3)
        r = self._post({'usar_ia': True, 'ai_variation_enabled': True})
        self.assertEqual(r.status_code, 201, r.content)
        c = EmailCampaign.objects.get()
        self.assertEqual(c.status, 'draft')
        self.assertFalse(c.ai_variation_enabled)
        self.assertFalse(c.schedule_config['ai_enabled'])
        self.assertEqual(c.schedule_config['batch_size'], 50)
        self.assertEqual(c.schedule_config['start_time'], '08:00')
        self.assertEqual(c.schedule_config['end_time'], '21:00')

    def test_la_respuesta_trae_donde_revisarla(self):
        _cliente('Ana Soto', 'ana@test.cl', 3)
        datos = self._post().json()
        self.assertTrue(datos['ok']); self.assertFalse(datos['repetida'])
        camp = datos['campanas'][0]
        c = EmailCampaign.objects.get()
        self.assertEqual(camp['id'], c.id)
        self.assertEqual(camp['destinatarios'], 1)
        self.assertEqual(camp['estado'], 'draft')
        self.assertEqual(camp['revisar_en'],
                         f'https://www.aremko.cl/admin/ventas/emailcampaign/{c.id}/change/')
        self.assertEqual(datos['universo'], 1); self.assertEqual(datos['sin_lote'], 0)

    def test_el_nombre_del_cliente_se_reemplaza_en_asunto_y_cuerpo(self):
        _cliente('María José Pérez', 'mj@test.cl', 3)
        self._post({'asunto': 'Hola {nombre_cliente}, mira'})
        d = EmailRecipient.objects.get()
        self.assertEqual(d.name, 'María')
        self.assertEqual(d.personalized_subject, 'Hola María, mira')
        self.assertIn('Hola María, esta semana', d.personalized_body)
        self.assertNotIn('{nombre_cliente}', d.personalized_body)
        # El template de la campaña conserva la variable para la vista previa.
        self.assertIn('{nombre_cliente}', EmailCampaign.objects.get().email_body_template)

    def test_el_nombre_por_defecto_lleva_la_fecha_de_hoy(self):
        _cliente('Ana Soto', 'ana@test.cl', 3)
        self._post()
        hoy = timezone.localtime(timezone.now()).date().isoformat()
        self.assertEqual(EmailCampaign.objects.get().name, f'Correo semanal {hoy}')

    def test_el_cuerpo_se_guarda_tal_cual_sin_pie(self):
        _cliente('Ana Soto', 'ana@test.cl', 3)
        self._post()
        self.assertEqual(EmailCampaign.objects.get().email_body_template, CUERPO)
        self.assertNotIn('unsubscribe', EmailRecipient.objects.get().personalized_body)


class ElTopeDeMil(Base):
    def _mil_y_tres(self):
        Cliente.objects.bulk_create([
            Cliente(nombre=f'Cliente {i}', email=f'c{i}@test.cl', telefono=f'+5690{i:07d}')
            for i in range(1003)])

    def test_un_lote_toma_mil_y_dice_cuantos_quedan(self):
        self._mil_y_tres()
        datos = self._post().json()
        self.assertEqual(datos['campanas'][0]['destinatarios'], 1000)
        self.assertEqual(datos['universo'], 1003)
        self.assertEqual(datos['sin_lote'], 3)
        self.assertEqual(EmailRecipient.objects.count(), 1000)

    def test_dos_lotes_son_disjuntos_y_se_numeran(self):
        self._mil_y_tres()
        datos = self._post({'lotes': 2, 'nombre': 'Semana 38'}).json()
        nombres = [c['nombre'] for c in datos['campanas']]
        self.assertEqual(nombres, ['Semana 38 · lote 1/2', 'Semana 38 · lote 2/2'])
        self.assertEqual([c['destinatarios'] for c in datos['campanas']], [1000, 3])
        correos = list(EmailRecipient.objects.values_list('email', flat=True))
        self.assertEqual(len(correos), len(set(correos)), 'un correo no puede ir en dos lotes')
        self.assertEqual(datos['sin_lote'], 0)

    def test_mas_lotes_que_gente_no_crea_campanas_vacias(self):
        _cliente('Ana Soto', 'ana@test.cl', 3)
        datos = self._post({'lotes': 3}).json()
        self.assertEqual(len(datos['campanas']), 1)
        self.assertEqual(EmailCampaign.objects.count(), 1)


class QuienEntraYQuienNo(Base):
    def _correos_en_el_lote(self):
        """Los correos de la campaña que creó ESTA llamada, no los de las fixtures."""
        r = self._post()
        self.assertEqual(r.status_code, 201, r.content)
        ids = [c['id'] for c in r.json()['campanas']]
        return sorted(EmailRecipient.objects.filter(campaign_id__in=ids)
                      .values_list('email', flat=True))

    def test_sin_correo_o_sin_arroba_no_entra(self):
        _cliente('Sin Correo', '', 3)
        Cliente.objects.create(nombre='Nulo', email=None, telefono='+56900000001')
        _cliente('Roto', 'no-es-correo', 3)
        _cliente('Ana Soto', 'ana@test.cl', 3)
        self.assertEqual(self._correos_en_el_lote(), ['ana@test.cl'])

    def test_lista_negra_activa_no_entra_pero_la_inactiva_si(self):
        _cliente('Baja', 'baja@test.cl', 3)
        _cliente('Vuelta', 'vuelta@test.cl', 3)
        EmailBlacklist.objects.create(email='baja@test.cl', reason='unsubscribe', domain='test.cl')
        EmailBlacklist.objects.create(email='vuelta@test.cl', reason='unsubscribe',
                                      domain='test.cl', is_active=False)
        self.assertEqual(self._correos_en_el_lote(), ['vuelta@test.cl'])

    def test_baja_del_newsletter_no_entra(self):
        _cliente('Baja', 'baja@test.cl', 3)
        _cliente('Ana Soto', 'ana@test.cl', 3)
        # Crear un Cliente con correo ya lo suscribe al newsletter; acá se da de baja.
        NewsletterSubscriber.objects.update_or_create(email='baja@test.cl',
                                                      defaults={'is_active': False})
        self.assertEqual(self._correos_en_el_lote(), ['ana@test.cl'])

    def test_un_correo_repetido_entre_clientes_entra_una_vez_y_en_minusculas(self):
        _cliente('Ana Soto', 'Ana@Test.cl', 3)
        _cliente('Ana S.', 'ana@test.cl', 30)
        self.assertEqual(self._correos_en_el_lote(), ['ana@test.cl'])

    def test_quien_ya_espera_en_otra_campana_no_entra(self):
        espera = _cliente('Espera', 'espera@test.cl', 3)
        _cliente('Ana Soto', 'ana@test.cl', 3)
        otra = EmailCampaign.objects.create(name='otra', email_subject_template='a',
                                            email_body_template='b', status='draft')
        EmailRecipient.objects.create(campaign=otra, client=espera, email='espera@test.cl',
                                      name='E', personalized_subject='a', personalized_body='b')
        self.assertEqual(self._correos_en_el_lote(), ['ana@test.cl'])

    def test_una_campana_terminada_no_retiene_a_nadie(self):
        libre = _cliente('Libre', 'libre@test.cl', 3)
        vieja = EmailCampaign.objects.create(name='vieja', email_subject_template='a',
                                             email_body_template='b', status='completed')
        EmailRecipient.objects.create(campaign=vieja, client=libre, email='libre@test.cl',
                                      name='L', personalized_subject='a', personalized_body='b',
                                      status='sent',
                                      sent_at=timezone.now() - datetime.timedelta(days=40))
        self.assertEqual(self._correos_en_el_lote(), ['libre@test.cl'])

    def test_quien_recibio_hace_menos_de_4_semanas_no_entra_pero_a_las_6_si(self):
        reciente = _cliente('Reciente', 'reciente@test.cl', 3)
        antiguo = _cliente('Antiguo', 'antiguo@test.cl', 3)
        vieja = EmailCampaign.objects.create(name='vieja', email_subject_template='a',
                                             email_body_template='b', status='completed')
        for c, dias in ((reciente, 10), (antiguo, 42)):
            EmailRecipient.objects.create(
                campaign=vieja, client=c, email=c.email, name='x', status='sent',
                personalized_subject='a', personalized_body='b',
                sent_at=timezone.now() - datetime.timedelta(days=dias))
        self.assertEqual(self._correos_en_el_lote(), ['antiguo@test.cl'])

    def test_nadie_elegible_es_400_y_no_crea_nada(self):
        _cliente('Baja', 'baja@test.cl', 3)
        EmailBlacklist.objects.create(email='baja@test.cl', reason='unsubscribe', domain='test.cl')
        r = self._post()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(EmailCampaign.objects.count(), 0)


class ElOrdenDeLaFila(Base):
    def test_compra_mas_reciente_primero_y_sin_compra_al_final(self):
        _cliente('Hace un año', 'anio@test.cl', 365)
        _cliente('Nunca compró', 'nunca@test.cl')
        _cliente('Hace dos días', 'dos@test.cl', 2)
        _cliente('Hace un mes', 'mes@test.cl', 30)
        self._post()
        fila = list(EmailRecipient.objects.order_by('id').values_list('email', flat=True))
        self.assertEqual(fila, ['dos@test.cl', 'mes@test.cl', 'anio@test.cl', 'nunca@test.cl'])

    def test_el_tope_corta_por_ese_orden(self):
        # Con tope 1.000 no se puede probar con 4 personas: se prueba que la
        # fila que devuelve el módulo respeta el orden y el lote toma la punta.
        from ventas.api_campana_semanal import fila_de_elegibles
        _cliente('Vieja', 'vieja@test.cl', 400)
        _cliente('Nueva', 'nueva@test.cl', 1)
        self.assertEqual([f['email'] for f in fila_de_elegibles()],
                         ['nueva@test.cl', 'vieja@test.cl'])


class LaMismaLlamadaDosVeces(Base):
    def test_no_duplica_y_devuelve_lo_que_ya_existe(self):
        _cliente('Ana Soto', 'ana@test.cl', 3)
        primera = self._post({'nombre': 'Semana 38'}).json()
        segunda = self._post({'nombre': 'Semana 38'})
        self.assertEqual(segunda.status_code, 200)
        self.assertTrue(segunda.json()['repetida'])
        self.assertEqual(segunda.json()['campanas'][0]['id'], primera['campanas'][0]['id'])
        self.assertEqual(EmailCampaign.objects.count(), 1)
        self.assertEqual(EmailRecipient.objects.count(), 1)

    def test_con_lotes_tampoco_duplica(self):
        Cliente.objects.bulk_create([
            Cliente(nombre=f'C {i}', email=f'c{i}@test.cl', telefono=f'+5690{i:07d}')
            for i in range(1001)])
        self._post({'nombre': 'Semana 38', 'lotes': 2})
        segunda = self._post({'nombre': 'Semana 38', 'lotes': 2}).json()
        self.assertTrue(segunda['repetida'])
        self.assertEqual(len(segunda['campanas']), 2)
        self.assertEqual(EmailCampaign.objects.count(), 2)


class LoQueSeRechaza(Base):
    def setUp(self):
        super().setUp()
        _cliente('Ana Soto', 'ana@test.cl', 3)

    def _400(self, cuerpo, pista):
        r = self._post(cuerpo)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn(pista, r.json()['error'])
        self.assertEqual(EmailCampaign.objects.count(), 0)

    def test_sin_asunto(self):
        self._400({'asunto': '  '}, 'asunto')

    def test_sin_cuerpo(self):
        self._400({'cuerpo_html': ''}, 'cuerpo')

    def test_cuerpo_de_mas_de_100_kb(self):
        self._400({'cuerpo_html': '<p>' + 'x' * (100 * 1024) + '</p>'}, '100 KB')

    def test_cuerpo_con_script(self):
        self._400({'cuerpo_html': '<p>hola</p><SCRIPT>alert(1)</SCRIPT>'}, 'script')

    def test_un_segmento_que_no_sea_todos(self):
        # Datamatic tenía segmentos por nombre; acá el lote lo arma Aremko.
        self._400({'segmento': 'recientes'}, 'segmento')

    def test_segmento_todos_si_se_acepta(self):
        self.assertEqual(self._post({'segmento': 'todos'}).status_code, 201)

    def test_lotes_fuera_de_rango(self):
        self._400({'lotes': 7}, 'lotes')
        self._400({'lotes': 0}, 'lotes')
        self._400({'lotes': 'muchos'}, 'lotes')

    def test_json_invalido(self):
        r = self.client.post(self.url, data='esto no es json', content_type='application/json',
                             HTTP_X_API_KEY=LLAVE)
        self.assertEqual(r.status_code, 400)
