"""Tests del Catálogo de Clips (H-070 Fase A).

Puros (SimpleTestCase): saneo del draft IA + validador de payload.
Con DB (TestCase, app aislada → sin drift): upsert idempotente, GET filtros, PATCH.
"""
import json

from django.test import SimpleTestCase, TestCase, override_settings

from .api_views import _validar_payload
from .models import Clip
from .tagging import sanear_draft, TAGGING_SYSTEM_PROMPT

KEY = 'test-key-h070'


class SanearDraftTest(SimpleTestCase):

    def test_draft_completo_valido(self):
        d = sanear_draft({
            'area': 'tina', 'nombre_comercial': 'Villarrica-Llaima', 'momento': 'atardecer',
            'estacion': 'invierno', 'vapor': 'sí', 'decoracion': 'con', 'personas': False,
            'permiso': 'libre', 'calidad': 'alta', 'keeper': True,
            'descripcion': 'Tina redonda humeante al atardecer', 'orientacion': 'horizontal',
            'estado': 'ok', 'etiquetas': ['tina', 'vapor'], 'apto_para': ['hero', 'blog'],
        })
        self.assertEqual(d['area'], 'tina')
        self.assertEqual(d['vapor'], 'sí')
        self.assertEqual(d['estado'], 'ok')
        self.assertTrue(d['keeper'])

    def test_valor_fuera_de_rango_cae_a_revisar(self):
        d = sanear_draft({'area': 'piscina', 'momento': 'madrugada'})
        self.assertEqual(d['area'], 'detalle')        # default conservador
        self.assertEqual(d['momento'], 'indistinto')
        self.assertEqual(d['estado'], 'revisar')      # dudoso → revisar

    def test_personas_fuerza_revisar_derechos_y_no_keeper(self):
        d = sanear_draft({'area': 'tina', 'personas': True, 'permiso': 'libre',
                          'keeper': True, 'estado': 'ok'})
        self.assertEqual(d['permiso'], 'revisar_derechos')
        self.assertFalse(d['keeper'])

    def test_basura_no_dict(self):
        d = sanear_draft('cualquier cosa')
        self.assertEqual(d['estado'], 'revisar')
        self.assertEqual(d['etiquetas'], [])

    def test_prompt_contiene_taxonomia_literal(self):
        for frase in ('Villarrica-Llaima', 'Tronador-Calbuco', 'Osorno-Hornopirén',
                      'Puyehue-Puntiagudo', 'Yates', 'Torre', 'Laurel', 'Sala Sol',
                      'pasarela', 'revisar_derechos'):
            self.assertIn(frase, TAGGING_SYSTEM_PROMPT, frase)


class ValidarPayloadTest(SimpleTestCase):

    def test_completo_ok(self):
        limpio, err = _validar_payload({
            'archivo': 'IMG_1.jpg', 'cloud_url': 'https://x/y.jpg', 'area': 'tina',
            'keeper': True, 'etiquetas': ['tina'], 'atributos': {'hidromasaje': True},
        })
        self.assertIsNone(err)
        self.assertEqual(limpio['area'], 'tina')
        self.assertEqual(limpio['atributos'], {'hidromasaje': True})

    def test_falta_archivo(self):
        _, err = _validar_payload({'cloud_url': 'https://x/y.jpg', 'area': 'tina'})
        self.assertIn('archivo', err)

    def test_choice_invalida(self):
        _, err = _validar_payload({'archivo': 'a.jpg', 'cloud_url': 'https://x', 'area': 'spa'})
        self.assertIn('area', err)

    def test_vapor_ia_permitido_al_operador(self):
        limpio, err = _validar_payload({'archivo': 'a.jpg', 'cloud_url': 'https://x',
                                        'area': 'tina', 'vapor': 'sí (IA)'})
        self.assertIsNone(err)
        self.assertEqual(limpio['vapor'], 'sí (IA)')

    def test_parcial_no_exige_obligatorios(self):
        limpio, err = _validar_payload({'keeper': False}, parcial=True)
        self.assertIsNone(err)
        self.assertEqual(limpio, {'keeper': False})


@override_settings(AUTOMATION_API_KEY=KEY)
class EndpointsCatalogoTest(TestCase):

    def _post(self, data):
        return self.client.post('/marketing/api/catalogo/', json.dumps(data),
                                content_type='application/json', HTTP_X_API_KEY=KEY)

    def test_auth_requerida(self):
        r = self.client.get('/marketing/api/catalogo/')
        self.assertEqual(r.status_code, 401)

    def test_upsert_idempotente_por_archivo(self):
        payload = {'archivo': 'IMG_9.jpg', 'cloud_url': 'https://res.cloudinary.com/x/a.jpg',
                   'area': 'tina', 'nombre_comercial': 'Yates', 'keeper': True}
        r1 = self._post(payload)
        self.assertEqual(r1.status_code, 201)
        payload['nombre_comercial'] = 'Tina Yates'
        r2 = self._post(payload)
        self.assertEqual(r2.status_code, 200)  # segunda vez: actualiza, no duplica
        self.assertEqual(Clip.objects.filter(archivo='IMG_9.jpg').count(), 1)
        self.assertEqual(Clip.objects.get(archivo='IMG_9.jpg').nombre_comercial, 'Tina Yates')

    def test_get_filtros(self):
        self._post({'archivo': 'a.jpg', 'cloud_url': 'https://x/a.jpg', 'area': 'tina',
                    'keeper': True, 'apto_para': ['hero']})
        self._post({'archivo': 'b.jpg', 'cloud_url': 'https://x/b.jpg', 'area': 'cabaña',
                    'keeper': False})
        r = self.client.get('/marketing/api/catalogo/?area=tina&keeper=true', HTTP_X_API_KEY=KEY)
        data = r.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['clips'][0]['archivo'], 'a.jpg')

    def test_patch_edita_y_no_toca_archivo(self):
        self._post({'archivo': 'c.jpg', 'cloud_url': 'https://x/c.jpg', 'area': 'tina'})
        clip = Clip.objects.get(archivo='c.jpg')
        r = self.client.patch(f'/marketing/api/catalogo/{clip.id}/',
                              json.dumps({'estado': 'revisar', 'archivo': 'HACK.jpg'}),
                              content_type='application/json', HTTP_X_API_KEY=KEY)
        self.assertEqual(r.status_code, 200)
        clip.refresh_from_db()
        self.assertEqual(clip.estado, 'revisar')
        self.assertEqual(clip.archivo, 'c.jpg')  # la clave de upsert no se edita
