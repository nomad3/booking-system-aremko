"""Tests del Catálogo de Clips (H-070 Fase A).

Puros (SimpleTestCase): saneo del draft IA + validador de payload.
Con DB (TestCase, app aislada → sin drift): upsert idempotente, GET filtros, PATCH.
"""
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from .api_views import _validar_payload
from .composer import (receta_normalizada, url_historia, lineas_normalizadas,
                        _offsets_abajo, _offsets_arriba, _offsets_centro, TAMANOS)
from .models import Clip
from .tagging import sanear_draft, TAGGING_SYSTEM_PROMPT
from .web_views import thumb_url, _elegir_diverso

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

    def test_detalle_con_boton_usar_en_historia_activo(self):
        # B2-A: el botón dejó de ser placeholder — ahora linkea al compositor.
        self.client.force_login(self.staff)
        clip = Clip.objects.get(archivo='t1.jpg')
        r = self.client.get(f'/marketing/catalogo/{clip.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Usar en historia')
        self.assertContains(r, f'/marketing/catalogo/componer/{clip.id}/')
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


CLOUD = 'https://res.cloudinary.com/x/image/upload/f_auto,q_auto/catalogo_clips/a.jpg'


class ComposerTest(SimpleTestCase):
    """B2-A: receta → URL Cloudinary (el server no pinta píxeles)."""

    def test_receta_normaliza_con_lista_blanca(self):
        r = receta_normalizada('  hola   río  ', posicion='volando', preset='neon')
        self.assertEqual(r['texto'], 'hola río')
        self.assertEqual(r['posicion'], 'abajo')   # default ante valor inválido
        self.assertEqual(r['preset'], 'velo')

    def test_preserva_saltos_de_linea_explicitos(self):
        """Jorge (2026-07-26): editar el texto en 2 líneas no se reflejaba —
        `_cap` colapsaba TODO a un solo párrafo, incluidos los `\\n` a propósito."""
        r = receta_normalizada('Línea uno\nLínea dos', 'abajo', 'velo')
        self.assertEqual(r['texto'], 'Línea uno\nLínea dos')

    def test_saltos_de_linea_limpian_espacios_repetidos_por_linea(self):
        r = receta_normalizada('  hola   río  \n  otra   línea  ', 'abajo', 'velo')
        self.assertEqual(r['texto'], 'hola río\notra línea')

    def test_lineas_en_blanco_al_principio_o_final_se_recortan(self):
        r = receta_normalizada('\n\nUno\nDos\n\n', 'abajo', 'velo')
        self.assertEqual(r['texto'], 'Uno\nDos')

    def test_url_compone_historia_9_16(self):
        u = url_historia(CLOUD, receta_normalizada('Aguas calientes', 'abajo', 'velo'))
        self.assertIn('c_fill,g_auto,w_1080,h_1920', u)
        # GlacialIndifference-Regular.otf: fuente de marca real (Jorge,
        # 2026-07-20), subida a Cloudinary como recurso raw/authenticated
        # (ver management command subir_fuente_historias) — se referencia con
        # su public_id + extensión. Sin "_bold_": peso regular, sin negrita.
        self.assertIn('l_text:GlacialIndifference-Regular.otf_58_center:', u)
        self.assertIn('c_fit,w_860', u)                        # wrap dentro de la capa
        self.assertIn('fl_layer_apply,g_south,y_380', u)       # colocación separada
        self.assertIn('co_rgb:F2E8D8', u)                      # texto crema del preset velo
        self.assertIn('GlacialIndifference-Regular.otf_26_letter_spacing_6_center', u)  # sello (spacing en el estilo)
        self.assertTrue(u.endswith('/f_auto,q_auto/catalogo_clips/a.jpg'))

    def test_texto_va_doble_encodeado(self):
        u = url_historia(CLOUD, receta_normalizada('río, bosque/vapor', 'centro', 'crema'))
        self.assertIn('r%25C3%25ADo%252C%2520bosque%252Fvapor', u)  # , / y acentos escapados

    def test_salto_de_linea_doble_encodeado_en_la_url(self):
        """Verificado contra Cloudinary real (curl + inspección visual del JPG,
        2026-07-26): %250A entre líneas renderiza como líneas separadas — misma
        mecánica de doble-encoding que ya usan la coma y el slash."""
        u = url_historia(CLOUD, receta_normalizada('Uno\nDos', 'abajo', 'velo'))
        self.assertIn('Uno%250ADos', u)

    def test_attachment_agrega_flag_descarga(self):
        u = url_historia(CLOUD, receta_normalizada('Hola', 'arriba', 'velo'), attachment=True)
        self.assertIn('fl_attachment:aremko_historia', u)

    def test_sin_texto_o_url_rara_devuelve_vacio(self):
        self.assertEqual(url_historia(CLOUD, receta_normalizada('')), '')
        self.assertEqual(url_historia('https://otra.cosa/x.jpg', receta_normalizada('Hola')), '')

    # -- "3 líneas con tamaño" + preset "transparente" (Jorge, 2026-07-26) --

    def test_lineas_normalizadas_descarta_vacias_y_acota_a_3(self):
        out = lineas_normalizadas([
            {'texto': '  Grande  ', 'tamano': 'grande'},
            {'texto': '   '},                              # vacía tras limpiar -> descartada
            {'texto': 'Chica', 'tamano': 'chico'},
            {'texto': 'Sobra', 'tamano': 'normal'},         # 4ta -> ignorada (MAX_LINEAS=3)
        ])
        self.assertEqual(out, [
            {'texto': 'Grande', 'tamano': 'grande'},
            {'texto': 'Chica', 'tamano': 'chico'},
        ])

    def test_lineas_normalizadas_tamano_invalido_degrada_a_normal(self):
        out = lineas_normalizadas([{'texto': 'Hola', 'tamano': 'gigante'}])
        self.assertEqual(out, [{'texto': 'Hola', 'tamano': 'normal'}])

    def test_lineas_normalizadas_ignora_entradas_no_dict(self):
        self.assertEqual(lineas_normalizadas(['no es un dict', 42, None]), [])
        self.assertEqual(lineas_normalizadas(None), [])

    def test_receta_normalizada_incluye_lineas(self):
        r = receta_normalizada('', 'abajo', 'transparente',
                                lineas=[{'texto': 'Desde $160.000', 'tamano': 'grande'}])
        self.assertEqual(r['lineas'], [{'texto': 'Desde $160.000', 'tamano': 'grande'}])
        self.assertEqual(r['preset'], 'transparente')

    def test_receta_sin_lineas_queda_lista_vacia(self):
        self.assertEqual(receta_normalizada('Hola')['lineas'], [])

    def test_url_con_lineas_arma_una_capa_por_linea_y_su_propio_tamano(self):
        receta = receta_normalizada('', 'abajo', 'velo', lineas=[
            {'texto': 'Chica arriba', 'tamano': 'chico'},
            {'texto': 'Grande abajo', 'tamano': 'grande'},
        ])
        u = url_historia(CLOUD, receta)
        self.assertIn(f'l_text:GlacialIndifference-Regular.otf_36_center:', u)  # chico=36px
        self.assertIn(f'l_text:GlacialIndifference-Regular.otf_80_center:', u)  # grande=80px
        # 2 capas de línea + 1 del sello = 3 fl_layer_apply en total.
        self.assertEqual(u.count('fl_layer_apply'), 3)

    def test_url_con_lineas_ignora_texto_plano_si_hay_lineas(self):
        """Si llena AMBOS (raro, pero posible en la URL), `lineas` manda —
        el modo clásico no debe aparecer mezclado en la misma imagen."""
        receta = receta_normalizada('Este texto no debería usarse', 'abajo', 'velo',
                                     lineas=[{'texto': 'Esta sí', 'tamano': 'normal'}])
        u = url_historia(CLOUD, receta)
        self.assertNotIn('Este%2520texto', u)
        self.assertIn('Esta%2520s%25C3%25AD', u)

    def test_preset_transparente_sin_caja_y_con_sombra(self):
        u = url_historia(CLOUD, receta_normalizada('Hola', 'abajo', 'transparente'))
        self.assertNotIn('b_rgb', u)  # sin caja (el sello tampoco lleva b_rgb en ningún preset)
        self.assertIn('e_shadow:60,co_black', u)
        self.assertIn('co_rgb:FFFFFF', u)

    def test_preset_velo_y_crema_no_llevan_sombra(self):
        u_velo = url_historia(CLOUD, receta_normalizada('Hola', 'abajo', 'velo'))
        u_crema = url_historia(CLOUD, receta_normalizada('Hola', 'abajo', 'crema'))
        self.assertNotIn('e_shadow', u_velo)
        self.assertNotIn('e_shadow', u_crema)

    def test_offsets_abajo_arriba_centro(self):
        """Fórmulas verificadas empíricamente contra Cloudinary real (curl +
        inspección visual de 3 líneas apiladas, 2026-07-26) antes de fijarlas."""
        self.assertEqual(_offsets_abajo([100, 50, 25]), [455, 405, 380])
        self.assertEqual(_offsets_arriba([100, 50, 25]), [300, 400, 450])
        self.assertEqual(_offsets_centro([100, 50, 25]), [-38, 38, 75])

    def test_offsets_1_sola_linea_coincide_con_posicion_clasica(self):
        """Con 1 sola línea, el offset debe coincidir con el POSICIONES clásico
        (380/300/0) — el modo multilínea no debe verse distinto del clásico
        cuando solo hay 1 línea."""
        self.assertEqual(_offsets_abajo([TAMANOS['normal'] * 1.35]), [380])
        self.assertEqual(_offsets_arriba([TAMANOS['normal'] * 1.35]), [300])
        self.assertEqual(_offsets_centro([TAMANOS['normal'] * 1.35]), [0])


class ComponerViewTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('angelica', 'a@x.cl', 'x', is_staff=True)
        cls.clip = Clip.objects.create(
            archivo='t9.jpg', cloud_url=CLOUD, area='tina',
            nombre_comercial='Llaima', descripcion='Tina humeante al atardecer')

    def test_anonimo_redirige(self):
        r = self.client.get(f'/marketing/catalogo/componer/{self.clip.id}/')
        self.assertEqual(r.status_code, 302)

    def test_default_usa_descripcion_del_clip(self):
        self.client.force_login(self.staff)
        r = self.client.get(f'/marketing/catalogo/componer/{self.clip.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Componer historia')
        self.assertContains(r, 'Tina humeante al atardecer')
        self.assertContains(r, 'c_fill,g_auto,w_1080,h_1920')  # preview compuesto
        self.assertContains(r, 'fl_attachment')                 # link de descarga

    def test_texto_y_preset_de_la_query(self):
        self.client.force_login(self.staff)
        r = self.client.get(f'/marketing/catalogo/componer/{self.clip.id}/',
                            {'texto': 'Noche junto al río', 'preset': 'crema', 'posicion': 'centro'})
        self.assertContains(r, 'co_rgb:1E4438')  # preset crema
        self.assertContains(r, 'g_center')

    def test_lineas_de_la_query_arman_preview_multilinea(self):
        """Modo "3 líneas con tamaño" (Jorge, 2026-07-26) llega por querystring
        (recarga de "Actualizar vista previa" o un link "Ver/Editar")."""
        self.client.force_login(self.staff)
        r = self.client.get(f'/marketing/catalogo/componer/{self.clip.id}/', {
            'preset': 'transparente', 'posicion': 'abajo',
            'linea1': 'Desde', 'linea1_tamano': 'chico',
            'linea2': '$160.000', 'linea2_tamano': 'grande',
        })
        self.assertContains(r, 'l_text:GlacialIndifference-Regular.otf_36_center:Desde')
        self.assertContains(r, 'l_text:GlacialIndifference-Regular.otf_80_center:')
        self.assertContains(r, 'e_shadow:60,co_black')  # sombra del preset transparente

    def test_preset_transparente_disponible_en_el_formulario(self):
        self.client.force_login(self.staff)
        r = self.client.get(f'/marketing/catalogo/componer/{self.clip.id}/')
        self.assertContains(r, 'value="transparente"')

    def test_clip_sin_cloud_url_404(self):
        vacio = Clip.objects.create(archivo='sin.jpg', area='detalle', cloud_url='')
        self.client.force_login(self.staff)
        r = self.client.get(f'/marketing/catalogo/componer/{vacio.id}/')
        self.assertEqual(r.status_code, 404)


# ============================================================================
# H-072 Fase 1: puente publicación → historia + registro de uso (UsoClip)
# ============================================================================
from datetime import date

from .models import UsoClip


class UsoClipModelTest(TestCase):

    def test_crea_uso_y_actualiza_ultimo_uso(self):
        clip = Clip.objects.create(archivo='u1.jpg', area='tina', cloud_url=CLOUD)
        self.assertIsNone(clip.ultimo_uso)
        UsoClip.objects.create(clip=clip, fecha=date(2026, 7, 25), canal='Instagram Stories', publicacion_id=42)
        clip.ultimo_uso = date(2026, 7, 25)
        clip.save(update_fields=['ultimo_uso'])
        clip.refresh_from_db()
        self.assertEqual(clip.ultimo_uso, date(2026, 7, 25))
        self.assertEqual(clip.usos.count(), 1)
        self.assertEqual(clip.usos.first().publicacion_id, 42)

    def test_publicacion_id_es_referencia_suave_sin_fk(self):
        # No debe existir integridad referencial real — un id inexistente no falla.
        clip = Clip.objects.create(archivo='u2.jpg', area='tina', cloud_url=CLOUD)
        uso = UsoClip.objects.create(clip=clip, fecha=date.today(), publicacion_id=999999)
        self.assertEqual(uso.publicacion_id, 999999)

    def test_to_dict_incluye_ultimo_uso(self):
        clip = Clip.objects.create(archivo='u3.jpg', area='tina', cloud_url=CLOUD, ultimo_uso=date(2026, 1, 1))
        self.assertEqual(clip.to_dict()['ultimo_uso'], '2026-01-01')


def _crear_pub(**kw):
    """Factory mínima de PublicacionPlanificada para los tests de enganche."""
    from marketing_briefs.models import PublicacionPlanificada
    defaults = dict(
        semana_inicio=date(2026, 7, 20), dia=date(2026, 7, 22),
        canal='Instagram Stories', tipo='story', pieza_key='story_miercoles',
        copy_json={'caption_completo': 'Una noche junto al río, sin apuro.'},
    )
    defaults.update(kw)
    return PublicacionPlanificada.objects.create(**defaults)


class EnganchePublicacionTest(TestCase):
    """H-072: el composer engancha la historia a la publicación (ORM directo,
    sin re-subir) + registra el uso del clip."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('angelica2', 'a2@x.cl', 'x', is_staff=True)
        cls.clip = Clip.objects.create(archivo='eng1.jpg', cloud_url=CLOUD, area='tina',
                                       nombre_comercial='Llaima')

    def _post_enganchar(self, pub, texto='Hola río', segmento=None):
        self.client.force_login(self.staff)
        data = {'texto': texto, 'posicion': 'abajo', 'preset': 'velo', 'pub_id': pub.id}
        if segmento is not None:
            data['segmento'] = segmento
        return self.client.post(f'/marketing/catalogo/componer/{self.clip.id}/enganchar/', data)

    def test_pieza_sin_segmentos_engancha_a_material_urls(self):
        pub = _crear_pub(tipo='post', canal='GBP', pieza_key='gbp_post', segmentos=[])
        r = self._post_enganchar(pub)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/marketing/publicaciones/', r.url)
        pub.refresh_from_db()
        self.assertEqual(len(pub.material_urls), 1)
        self.assertEqual(pub.material_meta[0]['tipo'], 'historia')
        self.assertEqual(pub.material_meta[0]['receta']['clip_id'], self.clip.id)
        self.assertEqual(pub.estado, 'lista')
        self.assertEqual(UsoClip.objects.filter(clip=self.clip, publicacion_id=pub.id).count(), 1)
        self.clip.refresh_from_db()
        self.assertEqual(self.clip.ultimo_uso, date.today())

    def test_pieza_con_lineas_engancha_y_persiste_lineas_en_la_receta(self):
        """Modo "3 líneas con tamaño" (Jorge, 2026-07-26): la receta guardada
        debe incluir `lineas` para que "Ver/Editar" la reabra tal cual."""
        pub = _crear_pub(tipo='post', canal='GBP', pieza_key='gbp_post_lineas', segmentos=[])
        self.client.force_login(self.staff)
        data = {
            'texto': '', 'posicion': 'abajo', 'preset': 'transparente', 'pub_id': pub.id,
            'linea1': 'Desde', 'linea1_tamano': 'chico',
            'linea2': '$160.000', 'linea2_tamano': 'grande',
        }
        r = self.client.post(f'/marketing/catalogo/componer/{self.clip.id}/enganchar/', data)
        self.assertEqual(r.status_code, 302)
        pub.refresh_from_db()
        self.assertEqual(pub.material_meta[0]['receta']['lineas'], [
            {'texto': 'Desde', 'tamano': 'chico'},
            {'texto': '$160.000', 'tamano': 'grande'},
        ])

    def test_pieza_con_segmentos_engancha_al_segmento_correcto(self):
        segs = [
            {'indice': 1, 'titulo': 'Historia 1', 'texto': 'Amanece', 'material_urls': [], 'material_meta': []},
            {'indice': 2, 'titulo': 'Historia 2', 'texto': 'Atardece', 'material_urls': [], 'material_meta': []},
        ]
        pub = _crear_pub(segmentos=segs, pieza_key='story_jueves', dia=date(2026, 7, 23))
        r = self._post_enganchar(pub, segmento=2)
        self.assertEqual(r.status_code, 302)
        pub.refresh_from_db()
        self.assertEqual(pub.segmentos[0]['material_urls'], [])          # historia 1 intacta
        self.assertEqual(len(pub.segmentos[1]['material_urls']), 1)      # historia 2 recibió el material
        self.assertEqual(pub.material_urls, [])                          # NO va a nivel pub

    def test_segmento_inexistente_no_rompe_y_redirige_con_error(self):
        pub = _crear_pub(segmentos=[{'indice': 1, 'titulo': 'Historia 1', 'texto': '', 'material_urls': [], 'material_meta': []}],
                         pieza_key='story_viernes', dia=date(2026, 7, 24))
        r = self._post_enganchar(pub, segmento=9)
        self.assertEqual(r.status_code, 302)
        self.assertIn('error=segmento_no_existe', r.url)
        pub.refresh_from_db()
        self.assertEqual(pub.segmentos[0]['material_urls'], [])
        self.assertFalse(UsoClip.objects.filter(clip=self.clip).exists())

    def test_publicacion_inexistente_no_rompe(self):
        r = self._post_enganchar(_PubStub(id=999999))
        self.assertEqual(r.status_code, 302)
        self.assertIn('error=sin_publicacion', r.url)

    def test_sin_texto_no_engancha(self):
        pub = _crear_pub(segmentos=[], pieza_key='gbp_post2', tipo='post', canal='GBP')
        r = self._post_enganchar(pub, texto='')
        self.assertEqual(r.status_code, 302)
        self.assertIn('error=sin_texto', r.url)
        pub.refresh_from_db()
        self.assertEqual(pub.material_urls, [])

    def test_no_reusa_uso_previo_registra_cada_vez(self):
        pub = _crear_pub(segmentos=[], pieza_key='gbp_post3', tipo='post', canal='GBP')
        self._post_enganchar(pub)
        self._post_enganchar(pub)
        self.assertEqual(UsoClip.objects.filter(clip=self.clip, publicacion_id=pub.id).count(), 2)


class _PubStub:
    """Objeto mínimo con `.id` para probar 'publicación inexistente' sin crear una real."""
    def __init__(self, id):
        self.id = id


class PublicacionesListaViewTest(TestCase):
    """H-072: pantalla /marketing/publicaciones/ (staff, lectura + botón Crear historia)."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('angelica3', 'a3@x.cl', 'x', is_staff=True)

    def test_anonimo_redirige(self):
        r = self.client.get('/marketing/publicaciones/')
        self.assertEqual(r.status_code, 302)

    def test_lista_tarjetas_de_la_semana(self):
        pub = _crear_pub(pieza_key='gbp_post_x', tipo='post', canal='GBP', segmentos=[],
                         copy_json={'caption_completo': 'Aguas calientes junto al río, hoy.'})
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/publicaciones/', {'semana': '2026-07-20'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'GBP')
        self.assertContains(r, 'Aguas calientes junto al río, hoy.')
        self.assertContains(r, f'pub_id={pub.id}')
        self.assertContains(r, '🤖 Automática')
        self.assertContains(r, 'disabled')

    def test_publicacion_con_historias_muestra_boton_por_segmento(self):
        segs = [
            {'indice': 1, 'titulo': 'Historia 1', 'texto': 'Uno', 'material_urls': [], 'material_meta': []},
            {'indice': 2, 'titulo': 'Historia 2', 'texto': 'Dos', 'material_urls': [], 'material_meta': []},
        ]
        pub = _crear_pub(segmentos=segs, pieza_key='story_lunes_x', dia=date(2026, 7, 20))
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/publicaciones/', {'semana': '2026-07-20'})
        self.assertContains(r, f'pub_id={pub.id}&segmento=1')
        self.assertContains(r, f'pub_id={pub.id}&segmento=2')

    def test_banner_confirmacion_enganche(self):
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/publicaciones/', {'enganchado': '7'})
        self.assertContains(r, 'enganchada a la publicación #7')

    def test_preview_de_historia_usa_la_foto_vigente_no_la_primera(self):
        """H-074: `urls[-1]` (la última enganchada) es la vigente — mismo
        criterio que ya usa revision_service para fotos/video. Antes de este
        fix, re-generar una historia no se reflejaba en la miniatura."""
        segs = [{'indice': 1, 'titulo': 'Historia 1', 'texto': 'Uno',
                'material_urls': ['https://res.cloudinary.com/x/vieja.jpg',
                                   'https://res.cloudinary.com/x/nueva.jpg'],
                'material_meta': []}]
        _crear_pub(segmentos=segs, pieza_key='story_preview_vigente', dia=date(2026, 7, 20))
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/publicaciones/', {'semana': '2026-07-20'})
        self.assertContains(r, 'nueva.jpg')
        self.assertNotContains(r, 'vieja.jpg')

    def test_material_preview_pub_level_usa_el_vigente(self):
        _crear_pub(segmentos=[], pieza_key='gbp_preview_vigente', tipo='post', canal='GBP',
                  material_urls=['https://res.cloudinary.com/x/vieja2.jpg',
                                 'https://res.cloudinary.com/x/nueva2.jpg'])
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/publicaciones/', {'semana': '2026-07-20'})
        self.assertContains(r, 'nueva2.jpg')
        self.assertNotContains(r, 'vieja2.jpg')

    def test_pendientes_lote_cuenta_solo_con_criterio_y_sin_material(self):
        segs = [
            {'indice': 1, 'titulo': 'H1', 'texto': 'a', 'material_urls': [],
             'criterio_foto': {'area': 'tina'}},                                 # cuenta
            {'indice': 2, 'titulo': 'H2', 'texto': 'b', 'material_urls': ['x'],
             'criterio_foto': {'area': 'tina'}},                                 # ya tiene material
            {'indice': 3, 'titulo': 'H3', 'texto': 'c', 'material_urls': []},     # sin criterio
        ]
        _crear_pub(segmentos=segs, pieza_key='story_pendientes', dia=date(2026, 7, 20))
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/publicaciones/', {'semana': '2026-07-20'})
        self.assertContains(r, '1 historia por generar')

    def test_boton_lote_dice_hoy_si_coincide_con_la_fecha_actual(self):
        # 'Generar las de hoy' por sí solo no alcanza: el atajo global de
        # arriba usa el MISMO texto también en su versión deshabilitada.
        # Se valida contra la URL concreta del lote (inequívoca) + que el
        # atajo global también se haya activado (no quedó en el fallback).
        # date.today() (NO timezone.now().date()): así compara contra la MISMA
        # referencia que usa la vista real (publicaciones_lista::hoy) — timezone.now()
        # es UTC y sin localizar da la fecha de mañana entre ~20:00 y medianoche Chile.
        hoy = date.today()
        lunes_de_hoy = hoy - timedelta(days=hoy.weekday())
        segs = [{'indice': 1, 'titulo': 'H1', 'texto': 'a', 'material_urls': [],
                'criterio_foto': {'area': 'tina'}}]
        pub = _crear_pub(semana_inicio=lunes_de_hoy, segmentos=segs,
                         pieza_key='story_hoy_lote', dia=hoy)
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/publicaciones/', {'semana': lunes_de_hoy.isoformat()})
        self.assertContains(r, f'/marketing/catalogo/lote/{pub.id}/')
        self.assertContains(r, 'Generar las de hoy')
        self.assertNotContains(r, 'No hay historias de hoy pendientes')  # atajo global activo, no en fallback

    def test_boton_lote_dice_todas_si_no_es_hoy(self):
        segs = [{'indice': 1, 'titulo': 'H1', 'texto': 'a', 'material_urls': [],
                'criterio_foto': {'area': 'tina'}}]
        pub = _crear_pub(segmentos=segs, pieza_key='story_no_hoy_lote', dia=date(2026, 7, 20))
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/publicaciones/', {'semana': '2026-07-20'})
        self.assertContains(r, f'/marketing/catalogo/lote/{pub.id}/')
        self.assertContains(r, 'Generar todas')

    def test_historia_con_material_muestra_ver_editar(self):
        """Jorge (2026-07-26): una historia ya generada no tenía forma de
        reabrirse para verla/descargarla/editarla — solo "Crear historia"
        (que manda al explorador a elegir una foto nueva desde cero)."""
        segs = [{'indice': 1, 'titulo': 'Historia 1', 'texto': 'Uno',
                'material_urls': ['https://res.cloudinary.com/x/h1.jpg'],
                'material_meta': [{'url': 'https://res.cloudinary.com/x/h1.jpg',
                                    'receta': {'texto': 'Río sonando fuerte', 'posicion': 'abajo',
                                               'preset': 'velo', 'clip_id': 77, 'tipo': 'historia'}}]}]
        pub = _crear_pub(segmentos=segs, pieza_key='story_vereditar', dia=date(2026, 7, 20))
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/publicaciones/', {'semana': '2026-07-20'})
        self.assertContains(r, '👁️ Ver / Editar')
        self.assertContains(r, '/marketing/catalogo/componer/77/')
        self.assertContains(r, f'pub_id={pub.id}&segmento=1')
        self.assertContains(r, 'texto=R%C3%ADo')  # urlencode del texto de la receta

    def test_ver_editar_con_lineas_arrastra_linea1_y_linea2_en_la_url(self):
        """Modo "3 líneas con tamaño" (Jorge, 2026-07-26): "Ver/Editar" debe
        reabrir el composer con las MISMAS líneas/tamaños, no solo `texto`."""
        segs = [{'indice': 1, 'titulo': 'Historia 1', 'texto': 'Uno',
                'material_urls': ['https://res.cloudinary.com/x/h3.jpg'],
                'material_meta': [{'url': 'https://res.cloudinary.com/x/h3.jpg',
                                    'receta': {'texto': '', 'posicion': 'abajo', 'preset': 'transparente',
                                               'lineas': [{'texto': 'Desde', 'tamano': 'chico'},
                                                          {'texto': '$160.000', 'tamano': 'grande'}],
                                               'clip_id': 77, 'tipo': 'historia'}}]}]
        pub = _crear_pub(segmentos=segs, pieza_key='story_vereditar_lineas', dia=date(2026, 7, 20))
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/publicaciones/', {'semana': '2026-07-20'})
        self.assertContains(r, 'linea1=Desde')
        self.assertContains(r, 'linea1_tamano=chico')
        self.assertContains(r, 'linea2_tamano=grande')

    def test_historia_con_material_sin_receta_no_rompe_y_sin_ver_editar(self):
        """Defensivo: material sin receta (caso hipotético/legado) no debe
        romper la página ni ofrecer un link que no se puede reconstruir."""
        segs = [{'indice': 1, 'titulo': 'Historia 1', 'texto': 'Uno',
                'material_urls': ['https://res.cloudinary.com/x/h2.jpg'],
                'material_meta': [{'url': 'https://res.cloudinary.com/x/h2.jpg'}]}]
        _crear_pub(segmentos=segs, pieza_key='story_sin_receta', dia=date(2026, 7, 20))
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/publicaciones/', {'semana': '2026-07-20'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '✓ lista')
        self.assertNotContains(r, '👁️ Ver / Editar')

    def test_pieza_sin_segmentos_con_material_muestra_ver_editar(self):
        pub = _crear_pub(segmentos=[], pieza_key='gbp_vereditar', tipo='post', canal='GBP',
                         material_urls=['https://res.cloudinary.com/x/gbp.jpg'],
                         material_meta=[{'url': 'https://res.cloudinary.com/x/gbp.jpg',
                                         'receta': {'texto': 'Un post boutique', 'posicion': 'centro',
                                                    'preset': 'crema', 'clip_id': 88, 'tipo': 'historia'}}])
        self.client.force_login(self.staff)
        r = self.client.get('/marketing/publicaciones/', {'semana': '2026-07-20'})
        self.assertContains(r, '👁️ Ver / Editar')
        self.assertContains(r, '/marketing/catalogo/componer/88/')
        self.assertContains(r, f'pub_id={pub.id}')


from datetime import timedelta

from .seleccionar import seleccionar_clip

_CRITERIO_TINA_NOCHE = {
    'area': 'tina', 'nombre_comercial': '', 'vapor_preferido': True,
    'decoracion': 'sin', 'momento': 'noche',
}


class SeleccionarClipTest(TestCase):
    """H-073 (Fase 2): cascada determinista de auto-pick — sin LLM, 100% código
    y auditable (nivel/aviso). area/nombre_comercial/vapor_preferido son duros
    en TODA la cascada; solo momento/decoración (3), no-repetir (4) y
    personas (5) ceden, siempre con aviso."""

    def _clip(self, **kw):
        n = Clip.objects.count()
        defaults = dict(archivo=f'sel-{n}.jpg', cloud_url=CLOUD, area='tina', estado='ok',
                        vapor='sí', decoracion='sin', momento='noche', personas=False)
        defaults.update(kw)
        return Clip.objects.create(**defaults)

    def test_nivel_1_keeper_fresca_gana(self):
        keeper = self._clip(keeper=True)
        clip, nivel, aviso = seleccionar_clip(_CRITERIO_TINA_NOCHE)
        self.assertEqual(clip.id, keeper.id)
        self.assertEqual(nivel, 1)
        self.assertEqual(aviso, '')

    def test_nivel_2_sin_exigir_keeper(self):
        c = self._clip(keeper=False)
        clip, nivel, aviso = seleccionar_clip(_CRITERIO_TINA_NOCHE)
        self.assertEqual(clip.id, c.id)
        self.assertEqual(nivel, 2)

    def test_nivel_3_relaja_momento_y_decoracion(self):
        c = self._clip(momento='dia', decoracion='con')  # no calza el criterio exacto
        clip, nivel, aviso = seleccionar_clip(_CRITERIO_TINA_NOCHE)
        self.assertEqual(clip.id, c.id)
        self.assertEqual(nivel, 3)

    def test_nivel_3_prefiere_keeper_como_desempate(self):
        self._clip(momento='dia', decoracion='con', keeper=False)
        keeper = self._clip(momento='dia', decoracion='con', keeper=True)
        clip, nivel, aviso = seleccionar_clip(_CRITERIO_TINA_NOCHE)
        self.assertEqual(clip.id, keeper.id)
        self.assertEqual(nivel, 3)

    def test_area_nombre_y_vapor_nunca_se_relajan(self):
        self._clip(area='masaje')          # otra área — nunca debe salir
        self._clip(area='tina', vapor='no')  # calza área pero no el vapor pedido
        clip, nivel, aviso = seleccionar_clip(_CRITERIO_TINA_NOCHE)
        self.assertIsNone(clip)
        self.assertEqual(nivel, 6)

    def test_nivel_4_permite_repetir_la_usada_hace_mas_tiempo(self):
        hoy = timezone.localtime(timezone.now()).date()  # misma referencia que usa seleccionar_clip
        vieja = self._clip(ultimo_uso=hoy - timedelta(days=5))
        self._clip(ultimo_uso=hoy - timedelta(days=1))
        clip, nivel, aviso = seleccionar_clip(_CRITERIO_TINA_NOCHE, dias=60)
        self.assertEqual(clip.id, vieja.id)
        self.assertEqual(nivel, 4)
        self.assertIn('repetida', aviso.lower())

    def test_fuera_de_la_ventana_de_dias_cuenta_como_fresca(self):
        hoy = timezone.localtime(timezone.now()).date()  # misma referencia que usa seleccionar_clip
        c = self._clip(keeper=True, ultimo_uso=hoy - timedelta(days=90))  # ventana default=60 → ya es fresca
        clip, nivel, aviso = seleccionar_clip(_CRITERIO_TINA_NOCHE, dias=60)
        self.assertEqual(clip.id, c.id)
        self.assertEqual(nivel, 1)

    def test_nivel_5_permite_personas_solo_si_se_autoriza_explicito(self):
        con_gente = self._clip(personas=True)
        clip, nivel, aviso = seleccionar_clip(_CRITERIO_TINA_NOCHE)  # permitir_personas=False default
        self.assertIsNone(clip)
        self.assertEqual(nivel, 6)
        clip, nivel, aviso = seleccionar_clip(_CRITERIO_TINA_NOCHE, permitir_personas=True)
        self.assertEqual(clip.id, con_gente.id)
        self.assertEqual(nivel, 5)
        self.assertIn('personas', aviso.lower())

    def test_estado_no_ok_nunca_sale_ni_degradando_todo(self):
        self._clip(estado='revisar')
        self._clip(estado='descartado', personas=True)
        clip, nivel, aviso = seleccionar_clip(_CRITERIO_TINA_NOCHE, permitir_personas=True)
        self.assertIsNone(clip)
        self.assertEqual(nivel, 6)

    def test_excluir_ids_salta_la_ya_mostrada(self):
        a = self._clip(keeper=True)
        b = self._clip(keeper=True)
        clip1, _, _ = seleccionar_clip(_CRITERIO_TINA_NOCHE)
        clip2, _, _ = seleccionar_clip(_CRITERIO_TINA_NOCHE, excluir_ids=[clip1.id])
        self.assertNotEqual(clip1.id, clip2.id)
        self.assertEqual({clip1.id, clip2.id}, {a.id, b.id})

    def test_nombre_comercial_filtra_por_icontains(self):
        yates = self._clip(nombre_comercial='Tina Yates')
        self._clip(nombre_comercial='Villarrica')
        criterio = dict(_CRITERIO_TINA_NOCHE, nombre_comercial='Yates')
        clip, nivel, aviso = seleccionar_clip(criterio)
        self.assertEqual(clip.id, yates.id)

    def test_criterio_invalido_devuelve_nivel_6_sin_lanzar(self):
        clip, nivel, aviso = seleccionar_clip({'area': ''})
        self.assertIsNone(clip)
        self.assertEqual(nivel, 6)
        clip, nivel, aviso = seleccionar_clip(None)
        self.assertIsNone(clip)
        self.assertEqual(nivel, 6)


_CRITERIO_LIBRE = {'area': 'tina', 'nombre_comercial': '', 'vapor_preferido': False,
                   'decoracion': '', 'momento': 'indistinto'}


class AutoGenerarViewTest(TestCase):
    """H-073 (Fase 2): la vista resuelve la foto sola vía seleccionar_clip y
    redirige al composer ya armado (o manda de vuelta al explorador con
    auto_error cuando no puede — sin criterio o sin foto disponible)."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('angelica5', 'a5@x.cl', 'x', is_staff=True)

    def setUp(self):
        self.client.force_login(self.staff)

    def _pub_con_historia(self, criterio_foto='__omitir__'):
        seg = {'indice': 1, 'titulo': 'Historia 1', 'texto': 'Uno', 'material_urls': [], 'material_meta': []}
        if criterio_foto != '__omitir__':
            seg['criterio_foto'] = criterio_foto
        return _crear_pub(segmentos=[seg], pieza_key='story_autogen', dia=date(2026, 7, 20))

    def test_anonimo_redirige_a_login(self):
        self.client.logout()
        r = self.client.get('/marketing/catalogo/auto-generar/', {'pub_id': 1, 'segmento': 1})
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r.url)

    def test_pub_inexistente_404(self):
        r = self.client.get('/marketing/catalogo/auto-generar/', {'pub_id': 999999})
        self.assertEqual(r.status_code, 404)

    def test_sin_criterio_foto_redirige_a_manual(self):
        pub = self._pub_con_historia(criterio_foto=None)
        r = self.client.get('/marketing/catalogo/auto-generar/', {'pub_id': pub.id, 'segmento': 1})
        self.assertEqual(r.status_code, 302)
        self.assertIn('auto_error=sin_criterio', r.url)

    def test_sin_foto_disponible_redirige_a_manual(self):
        pub = self._pub_con_historia(criterio_foto=_CRITERIO_LIBRE)  # sin ningún Clip creado
        r = self.client.get('/marketing/catalogo/auto-generar/', {'pub_id': pub.id, 'segmento': 1})
        self.assertEqual(r.status_code, 302)
        self.assertIn('auto_error=sin_foto', r.url)

    def test_encuentra_foto_y_redirige_al_composer(self):
        clip = Clip.objects.create(archivo='ag1.jpg', cloud_url=CLOUD, area='tina', keeper=True, estado='ok')
        pub = self._pub_con_historia(criterio_foto=_CRITERIO_LIBRE)
        r = self.client.get('/marketing/catalogo/auto-generar/', {'pub_id': pub.id, 'segmento': 1})
        self.assertEqual(r.status_code, 302)
        self.assertIn(f'/marketing/catalogo/componer/{clip.id}/', r.url)
        self.assertIn('auto=1', r.url)
        self.assertIn('nivel=1', r.url)
        self.assertIn(f'excluir={clip.id}', r.url)

    def test_otra_foto_salta_la_ya_mostrada(self):
        a = Clip.objects.create(archivo='ag2.jpg', cloud_url=CLOUD, area='tina', keeper=True, estado='ok')
        b = Clip.objects.create(archivo='ag3.jpg', cloud_url=CLOUD, area='tina', keeper=True, estado='ok')
        pub = self._pub_con_historia(criterio_foto=_CRITERIO_LIBRE)
        r1 = self.client.get('/marketing/catalogo/auto-generar/', {'pub_id': pub.id, 'segmento': 1})
        primero_id = int(r1.url.split('/componer/')[1].split('/')[0])
        r2 = self.client.get('/marketing/catalogo/auto-generar/',
                             {'pub_id': pub.id, 'segmento': 1, 'excluir': str(primero_id)})
        segundo_id = int(r2.url.split('/componer/')[1].split('/')[0])
        self.assertNotEqual(primero_id, segundo_id)
        self.assertEqual({primero_id, segundo_id}, {a.id, b.id})

    def test_componer_muestra_banner_auto_nivel_y_otra_foto(self):
        Clip.objects.create(archivo='ag4.jpg', cloud_url=CLOUD, area='tina', keeper=False, estado='ok')
        pub = self._pub_con_historia(criterio_foto=_CRITERIO_LIBRE)
        r = self.client.get('/marketing/catalogo/auto-generar/', {'pub_id': pub.id, 'segmento': 1}, follow=True)
        self.assertContains(r, 'Elegida automáticamente')
        self.assertContains(r, 'Otra foto')

    def test_pieza_sin_segmentos_usa_criterio_de_copy_json(self):
        pub = _crear_pub(segmentos=[], pieza_key='gbp_autogen', tipo='post', canal='GBP',
                         copy_json={'texto': 'Un post', 'criterio_foto': dict(_CRITERIO_LIBRE, area='recepcion')})
        clip = Clip.objects.create(archivo='ag5.jpg', cloud_url=CLOUD, area='recepcion', estado='ok')
        r = self.client.get('/marketing/catalogo/auto-generar/', {'pub_id': pub.id})
        self.assertEqual(r.status_code, 302)
        self.assertIn(f'/marketing/catalogo/componer/{clip.id}/', r.url)


class ElegirDiversoTest(TestCase):
    """H-074 (Fase 3): diversidad de nombre_comercial dentro de un lote —
    deseable, no obligatoria. Solo aplica a criterios genéricos
    (nombre_comercial vacío en el criterio); si el criterio ya pide una tina
    puntual, no hay nada que diversificar."""

    def _clip(self, nombre, **kw):
        n = Clip.objects.count()
        defaults = dict(archivo=f'div-{n}.jpg', cloud_url=CLOUD, area='tina', estado='ok',
                        keeper=True, nombre_comercial=nombre)
        defaults.update(kw)
        return Clip.objects.create(**defaults)

    def test_evita_repetir_nombre_comercial_si_hay_alternativa(self):
        villarrica = self._clip('Villarrica')
        yates = self._clip('Yates')
        clip1, _, _ = _elegir_diverso(_CRITERIO_LIBRE, set(), set())
        clip2, _, _ = _elegir_diverso(_CRITERIO_LIBRE, {clip1.id}, {clip1.nombre_comercial})
        self.assertNotEqual(clip1.nombre_comercial, clip2.nombre_comercial)
        self.assertEqual({clip1.id, clip2.id}, {villarrica.id, yates.id})

    def test_degrada_a_repetir_nombre_si_no_hay_alternativa(self):
        villarrica = self._clip('Villarrica')
        # "Villarrica" ya está en nombres_usados y es la ÚNICA disponible —
        # la diversidad no puede hacer fallar el ítem: la entrega igual.
        clip, nivel, aviso = _elegir_diverso(_CRITERIO_LIBRE, set(), {'Villarrica'})
        self.assertEqual(clip.id, villarrica.id)

    def test_criterio_con_nombre_puntual_no_diversifica(self):
        yates = self._clip('Yates')
        self._clip('Villarrica')  # no debería competir: el criterio pide Yates puntual
        criterio = dict(_CRITERIO_LIBRE, nombre_comercial='Yates')
        clip, nivel, aviso = _elegir_diverso(criterio, set(), {'Yates'})
        self.assertEqual(clip.id, yates.id)

    def test_sin_candidatas_devuelve_nivel_6(self):
        criterio = dict(_CRITERIO_LIBRE, area='entorno_region')
        clip, nivel, aviso = _elegir_diverso(criterio, set(), set())
        self.assertIsNone(clip)
        self.assertEqual(nivel, 6)


class GenerarLoteViewTest(TestCase):
    """H-074 (Fase 3): "⚡ Generar las de hoy" — batch de auto-pick para todas
    las historias auto-generables de una publicación, de una sola vez."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('angelica6', 'a6@x.cl', 'x', is_staff=True)

    def setUp(self):
        self.client.force_login(self.staff)

    def _segmentos(self):
        return [
            {'indice': 1, 'titulo': 'Historia 1', 'texto': 'Uno junto al río',
             'material_urls': [], 'material_meta': [], 'criterio_foto': dict(_CRITERIO_LIBRE)},
            {'indice': 2, 'titulo': 'Historia 2', 'texto': 'Dos junto al río',
             'material_urls': [], 'material_meta': [], 'criterio_foto': dict(_CRITERIO_LIBRE)},
            {'indice': 3, 'titulo': 'Historia 3 (ya enganchada)', 'texto': 'Tres',
             'material_urls': ['https://res.cloudinary.com/x/ya-existe.jpg'],
             'material_meta': [{'url': 'https://res.cloudinary.com/x/ya-existe.jpg'}],
             'criterio_foto': dict(_CRITERIO_LIBRE)},
            {'indice': 4, 'titulo': 'Historia 4 (sin criterio)', 'texto': 'Cuatro',
             'material_urls': [], 'material_meta': []},
        ]

    def test_genera_solo_las_auto_generables_sin_material(self):
        Clip.objects.create(archivo='lote1.jpg', cloud_url=CLOUD, area='tina',
                            nombre_comercial='Villarrica', keeper=True, estado='ok')
        Clip.objects.create(archivo='lote2.jpg', cloud_url=CLOUD, area='tina',
                            nombre_comercial='Yates', keeper=True, estado='ok')
        pub = _crear_pub(segmentos=self._segmentos(), pieza_key='story_lote1', dia=date(2026, 7, 20))
        r = self.client.post(f'/marketing/catalogo/lote/{pub.id}/')
        self.assertEqual(r.status_code, 302)
        self.assertIn(f'lote={pub.id}', r.url)
        pub.refresh_from_db()
        self.assertEqual(len(pub.segmentos[0]['material_urls']), 1)   # historia 1: generada
        self.assertEqual(len(pub.segmentos[1]['material_urls']), 1)   # historia 2: generada
        self.assertEqual(pub.segmentos[2]['material_urls'],
                        ['https://res.cloudinary.com/x/ya-existe.jpg'])  # historia 3: intacta
        self.assertEqual(pub.segmentos[3]['material_urls'], [])        # historia 4: sin criterio, intacta
        self.assertEqual(pub.estado, 'lista')
        self.assertEqual(UsoClip.objects.filter(publicacion_id=pub.id).count(), 2)

    def test_no_repite_foto_dentro_del_lote(self):
        Clip.objects.create(archivo='lote3.jpg', cloud_url=CLOUD, area='tina',
                            nombre_comercial='Villarrica', keeper=True, estado='ok')
        Clip.objects.create(archivo='lote4.jpg', cloud_url=CLOUD, area='tina',
                            nombre_comercial='Yates', keeper=True, estado='ok')
        pub = _crear_pub(segmentos=self._segmentos(), pieza_key='story_lote2', dia=date(2026, 7, 20))
        self.client.post(f'/marketing/catalogo/lote/{pub.id}/')
        pub.refresh_from_db()
        clip_ids = {pub.segmentos[0]['material_meta'][0]['receta']['clip_id'],
                   pub.segmentos[1]['material_meta'][0]['receta']['clip_id']}
        self.assertEqual(len(clip_ids), 2)

    def test_diversifica_nombre_comercial_cuando_hay_stock(self):
        Clip.objects.create(archivo='lote5.jpg', cloud_url=CLOUD, area='tina',
                            nombre_comercial='Villarrica', keeper=True, estado='ok')
        Clip.objects.create(archivo='lote6.jpg', cloud_url=CLOUD, area='tina',
                            nombre_comercial='Yates', keeper=True, estado='ok')
        pub = _crear_pub(segmentos=self._segmentos(), pieza_key='story_lote3', dia=date(2026, 7, 20))
        self.client.post(f'/marketing/catalogo/lote/{pub.id}/')
        pub.refresh_from_db()
        id1 = pub.segmentos[0]['material_meta'][0]['receta']['clip_id']
        id2 = pub.segmentos[1]['material_meta'][0]['receta']['clip_id']
        nombres = set(Clip.objects.filter(id__in=[id1, id2]).values_list('nombre_comercial', flat=True))
        self.assertEqual(nombres, {'Villarrica', 'Yates'})

    def test_resumen_cuenta_generadas_y_manual(self):
        Clip.objects.create(archivo='lote7.jpg', cloud_url=CLOUD, area='tina',
                            nombre_comercial='Villarrica', keeper=True, estado='ok')
        pub = _crear_pub(segmentos=self._segmentos(), pieza_key='story_lote4', dia=date(2026, 7, 20))
        r = self.client.post(f'/marketing/catalogo/lote/{pub.id}/', follow=True)
        # Con 1 sola foto disponible: historia 1 la toma, historia 2 se queda
        # sin candidata NUEVA (el lote no repite) + historia 4 sin criterio.
        self.assertContains(r, 'Generé 1 historia')
        self.assertContains(r, 'para Manual')

    def test_sin_stock_de_fotos_todas_van_a_manual(self):
        pub = _crear_pub(segmentos=self._segmentos(), pieza_key='story_lote5', dia=date(2026, 7, 20))
        r = self.client.post(f'/marketing/catalogo/lote/{pub.id}/', follow=True)
        pub.refresh_from_db()
        self.assertEqual(pub.segmentos[0]['material_urls'], [])
        self.assertEqual(pub.segmentos[1]['material_urls'], [])
        self.assertNotEqual(pub.estado, 'lista')
        self.assertContains(r, 'Generé 0 historias')

    def test_anonimo_redirige(self):
        self.client.logout()
        pub = _crear_pub(segmentos=[], pieza_key='story_lote6', dia=date(2026, 7, 20))
        r = self.client.post(f'/marketing/catalogo/lote/{pub.id}/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r.url)

    def test_get_no_permitido(self):
        pub = _crear_pub(segmentos=[], pieza_key='story_lote7', dia=date(2026, 7, 20))
        r = self.client.get(f'/marketing/catalogo/lote/{pub.id}/')
        self.assertEqual(r.status_code, 405)

    def test_pub_inexistente_404(self):
        r = self.client.post('/marketing/catalogo/lote/999999/')
        self.assertEqual(r.status_code, 404)
