"""Tests de marketing_briefs — foco en la derivación de piezas de TikTok (H-063).

El cross-post a TikTok reusa el MISMO video del Reel de Instagram, pero con
caption/hashtags nativos tomados del objeto anidado `tiktok` del copy. Estos
tests cubren el helper puro (`_derivar_pieza_tiktok`) y el `explode` completo
(que crea las filas de PublicacionPlanificada contra una DB de test).
"""
from datetime import date, timedelta

from django.test import TestCase

from marketing_briefs import services
from marketing_briefs.decisiones import caption_sin_editar, recolectar_decisiones
from marketing_briefs.models import PublicacionPlanificada
from ventas.services.marketing_brief_generator import (
    _incorporar_estilo_imagen,
    ESTILO_IMAGEN_AREMKO,
    _incorporar_estilo_video,
    ESTILO_VIDEO_AREMKO,
)


def _reel_ig(**over):
    """Un draft de Reel de Instagram con su objeto `tiktok` anidado."""
    base = {
        'necesario_esta_semana': True,
        'responsable': 'Angélica',
        'concepto': 'La tina al atardecer',
        'guion': [{'bloque': 'gancho_5s', 'texto': 'Mira esto'}],
        'tomas_sugeridas': ['toma del río'],
        'audio_sugerido': 'audio trending',
        'caption_completo': 'Caption largo y narrativo de Instagram...',
        'hashtags': ['#spa', '#puertovaras', '#instagram'],
        'tiktok': {
            'caption_completo': '¿Cuándo fue tu última pausa de verdad?',
            'hashtags': ['#fyp', '#spachile', '#puertovaras'],
        },
    }
    base.update(over)
    return base


class DerivarPiezaTikTokTests(TestCase):
    def test_usa_objeto_tiktok(self):
        ig = _reel_ig()
        tk = services._derivar_pieza_tiktok('reel_martes_tiktok', ig)
        # Caption y hashtags salen del objeto tiktok, no del de Instagram.
        self.assertEqual(tk['caption_completo'], '¿Cuándo fue tu última pausa de verdad?')
        self.assertEqual(tk['hashtags'], ['#fyp', '#spachile', '#puertovaras'])
        # El video es el mismo: guion/tomas/audio se conservan tal cual.
        self.assertEqual(tk['guion'], ig['guion'])
        self.assertEqual(tk['audio_sugerido'], ig['audio_sugerido'])
        # El objeto tiktok anidado no viaja dentro de la pieza derivada.
        self.assertNotIn('tiktok', tk)
        # Lleva el recordatorio operativo de exportar limpio.
        self.assertIn('nota_publicacion', tk)
        self.assertIn('watermark', tk['nota_publicacion'].lower())

    def test_no_muta_el_hermano(self):
        ig = _reel_ig()
        services._derivar_pieza_tiktok('reel_martes_tiktok', ig)
        # El hermano IG conserva su caption y su objeto tiktok intactos.
        self.assertEqual(ig['caption_completo'], 'Caption largo y narrativo de Instagram...')
        self.assertIn('tiktok', ig)

    def test_fallback_sin_objeto_tiktok(self):
        ig = _reel_ig()
        ig.pop('tiktok')
        tk = services._derivar_pieza_tiktok('reel_martes_tiktok', ig)
        # Sin copy nativo cae al de Instagram (el video igual debe publicarse).
        self.assertEqual(tk['caption_completo'], ig['caption_completo'])
        self.assertEqual(tk['hashtags'], ig['hashtags'])
        self.assertIn('nota_publicacion', tk)


class ExplodeTikTokTests(TestCase):
    LUNES = date(2026, 7, 20)

    def _brief(self):
        return {
            'drafts_completos': {
                'reel_martes': _reel_ig(),
                'reel_jueves': _reel_ig(concepto='El sauna después de la tina'),
            },
            'calendario_semanal': [
                {'dia': 'Martes', 'publicaciones': [{'tipo': 'reel', 'hora': '19:00'}]},
                {'dia': 'Jueves', 'publicaciones': [{'tipo': 'reel', 'hora': '20:00'}]},
            ],
        }

    def test_crea_fila_tiktok_junto_al_gemelo_ig(self):
        services.explode_brief_to_publicaciones(self.LUNES, self._brief())

        ig = PublicacionPlanificada.objects.get(semana_inicio=self.LUNES, pieza_key='reel_martes')
        tk = PublicacionPlanificada.objects.get(semana_inicio=self.LUNES, pieza_key='reel_martes_tiktok')

        self.assertEqual(tk.canal, 'TikTok')
        self.assertEqual(tk.tipo, 'reel')
        # Mismo día y misma hora que el Reel de Instagram (es el mismo video).
        self.assertEqual(tk.dia, ig.dia)
        self.assertEqual(tk.hora_sugerida, ig.hora_sugerida)
        self.assertEqual(tk.hora_sugerida, '19:00')
        # Caption nativo de TikTok, distinto al de Instagram.
        self.assertEqual(tk.copy_json['caption_completo'], '¿Cuándo fue tu última pausa de verdad?')
        self.assertNotEqual(tk.copy_json['caption_completo'], ig.copy_json['caption_completo'])

    def test_ambos_reels_generan_gemelo_tiktok(self):
        services.explode_brief_to_publicaciones(self.LUNES, self._brief())
        tiktoks = PublicacionPlanificada.objects.filter(semana_inicio=self.LUNES, canal='TikTok')
        self.assertEqual(tiktoks.count(), 2)
        self.assertEqual(
            set(tiktoks.values_list('pieza_key', flat=True)),
            {'reel_martes_tiktok', 'reel_jueves_tiktok'},
        )

    def test_sin_reel_no_crea_tiktok(self):
        brief = self._brief()
        brief['drafts_completos'].pop('reel_martes')  # esta semana no hay reel del martes
        services.explode_brief_to_publicaciones(self.LUNES, brief)
        self.assertFalse(
            PublicacionPlanificada.objects.filter(
                semana_inicio=self.LUNES, pieza_key='reel_martes_tiktok',
            ).exists()
        )
        # El del jueves sí, como control de que el brief no quedó vacío.
        self.assertTrue(
            PublicacionPlanificada.objects.filter(
                semana_inicio=self.LUNES, pieza_key='reel_jueves_tiktok',
            ).exists()
        )


class PromptImagenIATests(TestCase):
    """H-064: el prompt de edición de imagen debe llegar por-slide/por-historia
    (los helpers de segmentos hardcodean sus claves y lo perderían) y la línea de
    estilo boutique se sella determinísticamente, una sola vez."""

    def test_segmentos_slides_llevan_prompt_imagen(self):
        slides = [
            {'numero': 1, 'imagen_sugerida': 'tina', 'texto_overlay': 'A',
             'prompt_imagen_ia': 'acerca el encuadre a la tina'},
            {'numero': 2, 'imagen_sugerida': 'río', 'texto_overlay': 'B',
             'prompt_imagen_ia': 'sube el contraste del agua'},
        ]
        segs = services._segmentos_de_slides(slides)
        self.assertEqual([s['prompt_imagen_ia'] for s in segs],
                         ['acerca el encuadre a la tina', 'sube el contraste del agua'])

    def test_segmentos_historias_prompt_solo_en_foto(self):
        historias = [
            {'concepto': 'x', 'tipo': 'foto', 'texto_sugerido': 'A',
             'prompt_imagen_ia': 'recorta al centro'},
            {'concepto': 'y', 'tipo': 'encuesta', 'texto_sugerido': 'B'},  # sin foto
        ]
        segs = services._segmentos_de_historias(historias)
        self.assertEqual(segs[0]['prompt_imagen_ia'], 'recorta al centro')
        self.assertEqual(segs[1]['prompt_imagen_ia'], '')  # historia sin foto → vacío

    def test_estilo_se_sella_una_vez_y_verbatim(self):
        drafts = {
            'gbp_post': {'prompt_imagen_ia': 'ajusta la luz cálida'},
            'carrusel_miercoles': {'slides': [
                {'prompt_imagen_ia': 'encuadre a la tina'},
                {'texto_overlay': 'slide sin foto'},  # sin prompt
            ]},
            'stories_diarias': [
                {'dia': 'Lunes', 'historias': [
                    {'tipo': 'foto', 'prompt_imagen_ia': 'centra el río'},
                    {'tipo': 'encuesta'},  # sin prompt
                ]},
            ],
        }
        _incorporar_estilo_imagen(drafts)
        gbp = drafts['gbp_post']['prompt_imagen_ia']
        self.assertIn('ajusta la luz cálida', gbp)
        self.assertTrue(gbp.endswith(ESTILO_IMAGEN_AREMKO))
        self.assertEqual(gbp.count('Estética boutique íntima'), 1)  # una sola vez
        slides = drafts['carrusel_miercoles']['slides']
        self.assertTrue(slides[0]['prompt_imagen_ia'].endswith(ESTILO_IMAGEN_AREMKO))
        self.assertNotIn('prompt_imagen_ia', slides[1])  # sin foto → no se inventa
        historias = drafts['stories_diarias'][0]['historias']
        self.assertTrue(historias[0]['prompt_imagen_ia'].endswith(ESTILO_IMAGEN_AREMKO))
        self.assertNotIn('prompt_imagen_ia', historias[1])


class CaptionSinEditarTests(TestCase):
    """H-067: comparación TOLERANTE de captions (ratio ≥ 0.95, nunca igualdad)."""

    def test_igual_y_variantes_de_espacios(self):
        gen = "Una noche junto al río.\n\nReserva en el link."
        self.assertTrue(caption_sin_editar(gen, gen))
        self.assertTrue(caption_sin_editar(gen, "Una  noche junto al río. Reserva en el link."))

    def test_edicion_menor_pasa_el_umbral(self):
        gen = ("Una noche junto al río Pescado con tina caliente y bosque nativo. "
               "Reserva por el link de la bio y llega antes de las 20:00 para el atardecer.")
        pub = gen.replace("llega antes", "ven antes")  # retoque chico de la CM
        self.assertTrue(caption_sin_editar(gen, pub))

    def test_reescritura_cuenta_como_editado(self):
        self.assertFalse(caption_sin_editar(
            "Texto original largo del caption de prueba para el reel del martes",
            "Otro texto completamente distinto que escribió la community manager",
        ))

    def test_no_evaluable_devuelve_none(self):
        self.assertIsNone(caption_sin_editar("", "algo"))
        self.assertIsNone(caption_sin_editar("algo", None))
        self.assertIsNone(caption_sin_editar(None, None))


class DecisionesSemanaTests(TestCase):
    """H-067: bloque «Decisiones de la semana» desde métricas reales."""

    LUNES = date(2026, 7, 20)

    def _pub(self, semana, key, valiosa, reach, caption_pub=None, v=1):
        caption_gen = f'Caption generado de prueba para la pieza {key} del brief semanal'
        return PublicacionPlanificada.objects.create(
            semana_inicio=semana, dia=semana, canal='Instagram', tipo='reel',
            pieza_key=key, titulo=f'Pieza {key}',
            copy_json={'caption_completo': caption_gen},
            metricas={
                'v': v, 'fuente': 'instagram_graph',
                'caption_publicado': caption_pub if caption_pub is not None else caption_gen,
                'snapshots': [{'reach': reach, 'saves': 5, 'shares': 2}],
                'tasas': {'valiosa': valiosa, 'interaccion': 0.05},
            },
        )

    def test_bloque_con_ranking_y_meta_metrica(self):
        sem = self.LUNES - timedelta(weeks=1)
        self._pub(sem, 'reel_martes', 0.05, 1000)
        self._pub(sem, 'reel_jueves', 0.01, 500,
                  caption_pub='Reescrito completamente distinto por la community manager hoy')
        bloque = recolectar_decisiones(self.LUNES)
        self.assertIn('MEJOR FUNCIONÓ', bloque)
        self.assertIn('reel_martes', bloque)
        self.assertIn('valiosa 5.0%', bloque)
        self.assertIn('META-MÉTRICA', bloque)
        self.assertIn('50%', bloque)  # 1 de 2 evaluables sin editar
        self.assertIn('Decisiones de la semana', bloque)

    def test_sin_metricas_devuelve_vacio(self):
        self.assertEqual(recolectar_decisiones(self.LUNES), '')

    def test_metricas_sin_version_se_ignoran(self):
        sem = self.LUNES - timedelta(weeks=1)
        self._pub(sem, 'reel_x', 0.05, 100, v=None)  # sin 'v' → aún no cosechada
        self.assertEqual(recolectar_decisiones(self.LUNES), '')


class PromptVideoIATests(TestCase):
    """H-066: cada reel lleva 3 tomas {descripcion, prompt_video_ia} que deben
    llegar como segmentos (por clip) y con el estilo de video sellado. Ambos lados
    toleran el shape viejo de tomas como strings (briefs archivados)."""

    def test_segmentos_de_tomas_shape_nuevo(self):
        tomas = [
            {'descripcion': 'Clip 1 gancho', 'prompt_video_ia': 'paneo lento sobre la tina'},
            {'descripcion': 'Clip 2 cuerpo', 'prompt_video_ia': 'acercamiento al vapor'},
            {'descripcion': 'Clip 3 cierre', 'prompt_video_ia': 'el río corriendo'},
        ]
        segs = services._segmentos_de_tomas(tomas)
        self.assertEqual(len(segs), 3)
        self.assertEqual(segs[0]['titulo'], 'Clip 1')
        self.assertEqual(segs[0]['texto'], 'Clip 1 gancho')
        self.assertEqual(segs[0]['prompt_video_ia'], 'paneo lento sobre la tina')
        self.assertEqual(segs[2]['prompt_video_ia'], 'el río corriendo')

    def test_segmentos_de_tomas_tolera_shape_viejo(self):
        segs = services._segmentos_de_tomas(['Toma 1: la tina', 'Toma 2: el río'])
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0]['texto'], 'Toma 1: la tina')
        self.assertEqual(segs[0]['prompt_video_ia'], '')  # string viejo → sin prompt

    def test_estilo_video_se_sella_una_vez_y_tolera_strings(self):
        drafts = {
            'reel_martes': {'tomas_sugeridas': [
                {'descripcion': 'x', 'prompt_video_ia': 'paneo lento'},
                {'descripcion': 'y'},        # sin prompt
                'toma vieja string',         # shape viejo
            ]},
            'reel_jueves': {'tomas_sugeridas': [
                {'descripcion': 'z', 'prompt_video_ia': 'acercamiento'},
            ]},
        }
        _incorporar_estilo_video(drafts)
        t0 = drafts['reel_martes']['tomas_sugeridas'][0]['prompt_video_ia']
        self.assertIn('paneo lento', t0)
        self.assertTrue(t0.endswith(ESTILO_VIDEO_AREMKO))
        self.assertEqual(t0.count('Estética boutique íntima'), 1)  # sellado una sola vez
        # toma sin prompt → no se inventa; string vieja → intacta (no crashea)
        self.assertNotIn('prompt_video_ia', drafts['reel_martes']['tomas_sugeridas'][1])
        self.assertEqual(drafts['reel_martes']['tomas_sugeridas'][2], 'toma vieja string')
        # reel_jueves también sellado
        self.assertTrue(
            drafts['reel_jueves']['tomas_sugeridas'][0]['prompt_video_ia'].endswith(ESTILO_VIDEO_AREMKO)
        )
