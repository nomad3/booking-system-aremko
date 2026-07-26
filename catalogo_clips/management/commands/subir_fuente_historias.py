"""Sube la fuente de marca (Glacial Indifference, regular) a Cloudinary como
recurso raw/authenticated, para poder usarla en los l_text de las historias
del compositor (catalogo_clips/composer.py).

Comando de UNA SOLA VEZ. Se corre en la Shell de Render (ahí SÍ están las
credenciales reales de Cloudinary vía CLOUDINARY_STORAGE en settings.py —
localmente el SDK no está configurado). Seguro de re-correr (overwrite=True).

Decisión de marca (Jorge, 2026-07-20, ver skill local historia-aremko):
Glacial Indifference, peso NORMAL/regular, SIN negrita. Licencia SIL Open
Font License (libre uso comercial). Reemplaza "Montserrat" (fuente segura
de Cloudinary usada por defecto, no la de marca real).
"""
import os
import urllib.request
import urllib.error

from django.core.management.base import BaseCommand

FONT_PUBLIC_ID = 'GlacialIndifference-Regular'
FONT_FILENAME = 'GlacialIndifference-Regular.otf'


class Command(BaseCommand):
    help = 'Sube GlacialIndifference-Regular.otf a Cloudinary (raw/authenticated) para l_text'

    def handle(self, *args, **opts):
        import cloudinary
        import cloudinary.uploader

        ruta = os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'fonts', FONT_FILENAME)
        ruta = os.path.normpath(ruta)
        if not os.path.exists(ruta):
            self.stdout.write(self.style.ERROR(f'No encuentro el archivo: {ruta}'))
            return

        config = cloudinary.config()
        if not (config.cloud_name and config.api_key and config.api_secret):
            self.stdout.write(self.style.ERROR(
                'Cloudinary no está configurado en este entorno (faltan '
                'CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET) — este comando debe '
                'correr donde SÍ estén esas variables (Render, no local).'
            ))
            return

        self.stdout.write(f'Subiendo {ruta} ({os.path.getsize(ruta):,} bytes) a Cloudinary '
                          f'(cloud={config.cloud_name})...')
        try:
            resultado = cloudinary.uploader.upload(
                ruta,
                resource_type='raw',
                type='authenticated',
                public_id=FONT_PUBLIC_ID,
                overwrite=True,
            )
        except Exception as exc:  # noqa: BLE001 — reportar cualquier falla de la API con claridad
            self.stdout.write(self.style.ERROR(f'❌ Falló la subida: {exc}'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'✅ Subida OK: public_id={resultado.get("public_id")} '
            f'formato={resultado.get("format")} bytes={resultado.get("bytes")}'
        ))

        # Auto-verificación: un render real con l_text usando esta fuente,
        # contra el sample.jpg que trae por defecto toda cuenta Cloudinary
        # (no depende de tener un Clip real cargado).
        referencia_font = f'{FONT_PUBLIC_ID}.{resultado.get("format", "otf")}'
        url_prueba = (
            f'https://res.cloudinary.com/{config.cloud_name}/image/upload/'
            f'c_fill,g_auto,w_1080,h_1920/'
            f'l_text:{referencia_font}_58_center:Prueba%20de%20fuente,co_rgb:F2E8D8/'
            f'fl_layer_apply,g_south,y_380/sample.jpg'
        )
        self.stdout.write(f'Probando render con esta fuente: {url_prueba}')
        try:
            with urllib.request.urlopen(url_prueba, timeout=15) as r:
                self.stdout.write(self.style.SUCCESS(f'✅ Render de prueba OK: HTTP {r.status}'))
                self.stdout.write('Abre esa URL en el navegador para verla.')
        except urllib.error.HTTPError as exc:
            cuerpo = exc.read().decode('utf-8', errors='replace')[:500]
            self.stdout.write(self.style.ERROR(f'❌ Render de prueba falló: HTTP {exc.code}\n{cuerpo}'))
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.ERROR(f'❌ Render de prueba falló: {exc}'))
