"""Diagnóstico H-065/H-066 F2: prueba la revisión IA de video POR CLIP contra un
video real ya subido a Cloudinary (el hero de la landing de masajes), end-to-end:
metadata vía Admin API → fotogramas por URL (so_<seg>) → modelo con visión →
persistencia en el segmento. No toca la cola real: crea una publicación de
prueba (pieza_key 'diagnostico_video_h065', estado no_aplica), la revisa y la
borra al final.

Uso (Shell de Render o job, sin argumentos):
    python manage.py diagnosticar_revision_video
"""
import os
from datetime import date, timedelta

from django.core.management.base import BaseCommand

# Video real de Cloudinary (hero de /masajes/): sirve de conejillo. Es
# vertical 9:16 (608×1080), así que el caso feliz del checklist de formato.
VIDEO_URL = 'https://res.cloudinary.com/dtuncr1pi/video/upload/v1/IMG_4138_web_soihdc.mp4'
PUBLIC_ID = 'IMG_4138_web_soihdc'


class Command(BaseCommand):
    help = 'Prueba la revisión IA de video por clip (H-065/H-066 F2) con un video real de Cloudinary'

    def handle(self, *args, **options):
        from marketing_briefs.api_views import _ratio_label
        from marketing_briefs.models import PublicacionPlanificada
        from marketing_briefs import revision_service as rs

        hoy = date.today()
        lunes = hoy - timedelta(days=hoy.weekday())

        # 1) Metadata real del video vía Admin API (mismo SDK que usa la subida
        #    de video — de paso valida que Cloudinary esté configurado en prod).
        meta = {'url': VIDEO_URL, 'tipo': 'video'}
        try:
            import cloudinary
            import cloudinary.api
            if not cloudinary.config().cloud_name:
                cloudinary.config(
                    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
                    api_key=os.getenv('CLOUDINARY_API_KEY'),
                    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
                    secure=True,
                )
            r = cloudinary.api.resource(PUBLIC_ID, resource_type='video')
            w, h = r.get('width'), r.get('height')
            if w and h:
                ratio, orient = _ratio_label(w, h)
                meta.update({'width': int(w), 'height': int(h), 'ratio': ratio, 'orientacion': orient})
            if r.get('duration'):
                meta['duration'] = round(float(r['duration']), 1)
            self.stdout.write(f"Metadata Cloudinary OK: {w}×{h} ({meta.get('orientacion')}), "
                              f"duración {meta.get('duration') or 'no reportada'}")
        except Exception as exc:  # noqa: BLE001 — el diagnóstico sigue sin metadata
            self.stdout.write(f'Admin API sin metadata ({exc}) — sigo con fallback')
        if not meta.get('duration'):
            # La Admin API no reporta duration (solo la respuesta del UPLOAD la
            # trae, y ese es el camino real). Para ejercitar los 4 fotogramas
            # del clip en el diagnóstico, asumimos una duración típica.
            meta['duration'] = 8.0
            self.stdout.write('Duración asumida 8.0s (solo para el diagnóstico; en la subida real viene del upload)')

        # 2) Fotogramas derivados por URL (lo nuevo de H-065, sin ffmpeg).
        frames, offsets = rs._urls_frames_video(VIDEO_URL, meta.get('duration'), 'clip')
        self.stdout.write(f'Fotogramas derivados ({len(frames)}), a los segundos {offsets}:')
        for u in frames:
            self.stdout.write(f'  {u}')

        # 3) Publicación de prueba con un segmento sintético realista.
        pub, _ = PublicacionPlanificada.objects.get_or_create(
            semana_inicio=lunes, pieza_key='diagnostico_video_h065',
            defaults=dict(
                dia=lunes, canal='Instagram', tipo='reel', estado='no_aplica',
                titulo='[DIAGNÓSTICO H-065] Clip de prueba',
                copy_json={'duracion_objetivo_segundos': 30,
                           'guion': [{'bloque': 'gancho_5s', 'texto': 'La tina humeando junto al río'}]},
            ),
        )
        pub.segmentos = [{
            'indice': 1, 'titulo': 'Clip 1',
            'texto': 'Clip 1 — GANCHO: la tina humeando junto al río al atardecer',
            'prompt_video_ia': ('Anima la foto real: paneo lento hacia la tina, vapor subiendo. '
                                'No agregues personas ni objetos.'),
            'material_urls': [VIDEO_URL], 'material_meta': [meta],
            'revision_veredicto': 'revisando', 'revision_json': [],
            'revision_resumen': '', 'revision_at': None,
        }]
        pub.save(update_fields=['segmentos', 'updated_at'])

        # 4) Revisión síncrona (acá esperamos al modelo; en la API real va en thread).
        self.stdout.write('Llamando al revisor (modelo con visión)...')
        r = rs.revisar_segmento(pub, 1)
        self.stdout.write(self.style.SUCCESS(f"VEREDICTO: {r['veredicto']}"))
        self.stdout.write(f"RESUMEN: {r['resumen']}")
        for c in r.get('correcciones') or []:
            self.stdout.write(f"- [{c.get('severidad')}] {c.get('aspecto')}: "
                              f"{c.get('encontrado')} → {c.get('correccion')}")

        # 5) Limpieza total.
        pub.delete()
        self.stdout.write('Publicación de prueba borrada. Diagnóstico completo.')
