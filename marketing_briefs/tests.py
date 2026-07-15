"""Tests de marketing_briefs — foco en la derivación de piezas de TikTok (H-063).

El cross-post a TikTok reusa el MISMO video del Reel de Instagram, pero con
caption/hashtags nativos tomados del objeto anidado `tiktok` del copy. Estos
tests cubren el helper puro (`_derivar_pieza_tiktok`) y el `explode` completo
(que crea las filas de PublicacionPlanificada contra una DB de test).
"""
from datetime import date

from django.test import TestCase

from marketing_briefs import services
from marketing_briefs.models import PublicacionPlanificada


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
