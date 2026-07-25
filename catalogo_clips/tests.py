"""Tests del Catálogo de Clips (H-070 Fase A).

Puros (SimpleTestCase): saneo del draft IA + validador de payload.
Con DB (TestCase, app aislada → sin drift): upsert idempotente, GET filtros, PATCH.
"""
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from .api_views import _validar_payload
from .models import Clip
from .tagging import sanear_draft, TAGGING_SYSTEM_PROMPT
from .web_views import thumb_url

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


class ThumbUrlTest(SimpleTestCase):

    def test_inserta_transformacion(self):
        u = 'https://res.cloudinary.com/x/image/upload/v1/catalogo_clips/a.jpg'
        self.assertEqual(
            thumb_url(u),
            'https://res.cloudinary.com/x/image/upload/w_400,c_fill,ar_4:5,q_auto,f_auto/v1/catalogo_clips/a.jpg')

    def test_encadena_si_ya_hay_transformacion(self):
        u = 'https://res.cloudinary.com/x/image/upload/f_auto,q_auto/catalogo_clips/a.jpg'
        self.assertTrue(thumb_url(u).startswith(
            'https://res.cloudinary.com/x/image/upload/w_400,c_fill,ar_4:5,q_auto,f_auto/f_auto,q_auto/'))

    def test_url_rara_no_explota(self):
        self.assertEqual(thumb_url(''), '')
        self.assertEqual(thumb_url('https://otra.cosa/img.jpg'), 'https://otra.cosa/img.jpg')


class ExploradorWebTest(TestCase):
    """H-071 B1: el explorador exige staff (no superuser) y filtra server-side."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('angelica', 'a@x.cl', 'x', is_staff=True)
        Clip.objects.create(archivo='t1.jpg', cloud_url='https://res.cloudinary.com/x/image/upload/v1/t1.jpg',
                            area='tina', nombre_comercial='Llaima', keeper=True, vapor='sí',
                            momento='noche', estado='ok')
        Clip.objects.create(archivo='c1.jpg', cloud_url='https://res.cloudinary.com/x/image/upload/v1/c1.jpg',
                            area='cabaña', nombre_comercial='Torre', estado='ok')
        Clip.objects.create(archivo='d1.jpg', cloud_url='https://res.cloudinary.com/x/image/upload/v1/d1.jpg',
                            area='detalle', estado='descartado')

    def test_anonimo_redirige_a_login(self):
        r = self.client.get('/marketing/catalogo/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r.url)

    def test_staff_no_superuser_entra(self):
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/catalogo/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Catálogo de fotos')
        # Default: la descartada NO aparece (2 visibles). Se asserta por `archivo`
        # (alt de la card) porque los nombres salen igual en el dropdown de filtros.
        self.assertContains(r, 't1.jpg')
        self.assertContains(r, 'c1.jpg')
        self.assertNotContains(r, 'd1.jpg')

    def test_toggle_todas_incluye_descartadas(self):
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/catalogo/?todas=1')
        self.assertContains(r, 'd1.jpg')

    def test_filtros_area_y_keeper(self):
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/catalogo/?area=tina&keeper=1')
        self.assertContains(r, 't1.jpg')
        self.assertNotContains(r, 'c1.jpg')

    def test_busqueda_q(self):
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/catalogo/?q=torre')
        self.assertContains(r, 'c1.jpg')
        self.assertNotContains(r, 't1.jpg')

    def test_thumb_chico_en_grid_no_1440(self):
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/catalogo/')
        self.assertContains(r, 'w_400,c_fill')  # miniatura derivada, no la master

    def test_detalle_con_boton_b2_deshabilitado(self):
        self.client.force_login(self.staff)
        clip = Clip.objects.get(archivo='t1.jpg')
        r = self.client.get(f'/marketing/catalogo/{clip.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Usar en historia')
        self.assertContains(r, 'disabled')
        self.assertContains(r, 'Vapor')


class IngestaWebTest(TestCase):
    """B1.5: Angélica sube la foto → IA propone → confirma → catálogo."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('angelica', 'a@x.cl', 'x', is_staff=True)

    def _foto(self, nombre='IMG_9999.jpg'):
        return SimpleUploadedFile(nombre, b'\xff\xd8\xff\xe0fakejpg', content_type='image/jpeg')

    def test_anonimo_redirige(self):
        r = self.client.get('/marketing/catalogo/ingesta/')
        self.assertEqual(r.status_code, 302)

    def test_get_muestra_form_subida(self):
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/catalogo/ingesta/')
        self.assertContains(r, 'Subir una foto al catálogo')

    def test_heic_da_mensaje_amable(self):
        self.client.force_login(self.staff)
        r = self.client.post('/marketing/catalogo/ingesta/',
                             {'imagen': self._foto('IMG_1.heic')})
        self.assertContains(r, 'Formato no soportado')
        self.assertContains(r, 'iPhone')

    @patch('catalogo_clips.web_views.etiquetar_imagen')
    @patch('catalogo_clips.web_views._subir_imagen_optimizada')
    def test_subida_muestra_draft_ia(self, mock_subir, mock_ia):
        mock_subir.return_value = {'cloud_url': 'https://res.cloudinary.com/x/image/upload/f_auto,q_auto/catalogo_clips/z.jpg',
                                   'width': 1440, 'height': 1080}
        mock_ia.return_value = {'area': 'tina', 'nombre_comercial': 'Villarrica-Llaima',
                                'momento': 'atardecer', 'estacion': 'indistinto', 'vapor': 'sí',
                                'decoracion': 'con', 'personas': False, 'permiso': 'libre',
                                'calidad': 'alta', 'keeper': True, 'descripcion': 'Tina humeante',
                                'orientacion': '', 'estado': 'ok',
                                'etiquetas': ['tina', 'vapor'], 'apto_para': ['hero']}
        self.client.force_login(self.staff)
        r = self.client.post('/marketing/catalogo/ingesta/', {'imagen': self._foto()})
        self.assertContains(r, 'Revisa y confirma')
        self.assertContains(r, 'Villarrica-Llaima')
        self.assertContains(r, 'IMG_9999.jpg')
        # La orientación vacía del draft se completa con las dimensiones reales.
        self.assertContains(r, 'horizontal')

    def test_guardar_crea_clip_y_redirige(self):
        self.client.force_login(self.staff)
        r = self.client.post('/marketing/catalogo/ingesta/guardar/', {
            'archivo': 'IMG_9999.jpg',
            'cloud_url': 'https://res.cloudinary.com/x/image/upload/z.jpg',
            'area': 'tina', 'nombre_comercial': 'Llaima', 'momento': 'noche',
            'estacion': 'indistinto', 'vapor': 'sí', 'decoracion': 'con',
            'calidad': 'alta', 'estado': 'ok', 'descripcion': 'Tina de noche',
            'etiquetas': 'tina, vapor, noche', 'apto_para': ['hero', 'historia'],
            'keeper': '1', 'orientacion': 'vertical', 'permiso': 'libre',
        })
        self.assertEqual(r.status_code, 302)
        clip = Clip.objects.get(archivo='IMG_9999.jpg')
        self.assertIn(f'/marketing/catalogo/{clip.id}/', r.url)
        self.assertEqual(clip.area, 'tina')
        self.assertEqual(clip.etiquetas, ['tina', 'vapor', 'noche'])
        self.assertEqual(clip.apto_para, ['hero', 'historia'])
        self.assertTrue(clip.keeper)
        self.assertEqual(clip.fuente, 'ingesta_web')

    def test_guardar_con_personas_fuerza_revisar_derechos(self):
        self.client.force_login(self.staff)
        self.client.post('/marketing/catalogo/ingesta/guardar/', {
            'archivo': 'IMG_P.jpg', 'cloud_url': 'https://x/p.jpg', 'area': 'masaje',
            'personas': '1', 'permiso': 'libre',
        })
        self.assertEqual(Clip.objects.get(archivo='IMG_P.jpg').permiso, 'revisar_derechos')

    def test_guardar_sin_area_reintenta_con_error(self):
        self.client.force_login(self.staff)
        r = self.client.post('/marketing/catalogo/ingesta/guardar/', {
            'archivo': 'IMG_X.jpg', 'cloud_url': 'https://x/x.jpg',
        })
        self.assertEqual(r.status_code, 200)  # re-render del form con el error
        self.assertContains(r, 'area')
        self.assertFalse(Clip.objects.filter(archivo='IMG_X.jpg').exists())
