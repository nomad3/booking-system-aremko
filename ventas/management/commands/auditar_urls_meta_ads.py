# -*- coding: utf-8 -*-
"""Audita a QUÉ URL de aremko.cl apunta cada anuncio de Meta.

Nació de la separación H-087 (`/experiencia-romantica/` dejó de ofrecer cumpleaños
y despedidas, que se mudaron a `/celebraciones/`): había que saber si alguna
campaña viva manda tráfico de cumpleaños a la landing romántica. La URL vieja
sigue existiendo —no hay 404— pero ya no vende esa ocasión.

Corre en Render, que es donde vive `META_SYSTEM_USER_TOKEN` (local no lo tiene).

Cómo encuentra las URLs: NO adivina la ruta dentro del creativo. Los anuncios de
Meta guardan el destino en lugares distintos según el tipo (link_data, video_data,
asset_feed_spec, call_to_action…), así que pide el creativo completo y BUSCA
RECURSIVAMENTE cualquier string que parezca URL. Así ningún formato se escapa.

Uso:
    python manage.py auditar_urls_meta_ads                  # solo anuncios ACTIVE
    python manage.py auditar_urls_meta_ads --todos          # incluye pausados
    python manage.py auditar_urls_meta_ads --dominio otra.cl
"""
import re

from django.core.management.base import BaseCommand

from ventas.services.meta_reporter import _get, list_accessible_ad_accounts

# Campos del creativo donde Meta puede esconder el destino. Se piden todos y
# después se escanea el JSON completo: más barato que mantener rutas a mano.
CREATIVE_FIELDS = (
    'object_story_spec,asset_feed_spec,link_destination_display_url,'
    'template_url,url_tags,effective_object_story_id,name'
)

# El esquema es OPCIONAL a propósito: `link_destination_display_url` llega como
# "aremko.cl/celebraciones", sin http://. Esto también engancha ruido tipo
# "object_story_spec.link_data", pero es inofensivo: abajo solo se conservan las
# coincidencias que contienen el dominio vigilado.
RE_URL = re.compile(r'(?:https?://)?[\w.-]+\.[a-z]{2,}(?:/[^\s"\'<>\\),]*)?', re.IGNORECASE)

# Rutas que este comando vigila (las dos puertas de H-087).
RUTA_ROMANTICA = '/experiencia-romantica'
RUTA_CELEBRACIONES = '/celebraciones'


def _urls_en(nodo):
    """Todas las URLs dentro de una estructura anidada, sin asumir su forma."""
    encontradas = []
    if isinstance(nodo, str):
        encontradas.extend(RE_URL.findall(nodo))
    elif isinstance(nodo, dict):
        for valor in nodo.values():
            encontradas.extend(_urls_en(valor))
    elif isinstance(nodo, (list, tuple)):
        for valor in nodo:
            encontradas.extend(_urls_en(valor))
    return encontradas


def _paginar(path, params, max_paginas=20):
    """Recorre las páginas de un edge de Graph API y devuelve todos los items."""
    items = []
    data = _get(path, params)
    for _ in range(max_paginas):
        items.extend(data.get('data', []))
        siguiente = (data.get('paging') or {}).get('cursors', {}).get('after')
        if not siguiente or not data.get('paging', {}).get('next'):
            break
        data = _get(path, dict(params, after=siguiente))
    return items


class Command(BaseCommand):
    help = 'Lista a qué URL apunta cada anuncio de Meta (para cazar links a landings que cambiaron).'

    def add_arguments(self, parser):
        parser.add_argument('--todos', action='store_true',
                            help='Incluye anuncios pausados/archivados (default: solo ACTIVE).')
        parser.add_argument('--dominio', default='aremko.cl',
                            help='Dominio a vigilar. Default: aremko.cl')

    def handle(self, *args, **opts):
        dominio = opts['dominio'].lower()
        solo_activos = not opts['todos']

        self.stdout.write(self.style.SUCCESS(
            f"\n🔎 URLs de {dominio} en los anuncios de Meta "
            f"({'solo ACTIVE' if solo_activos else 'todos los estados'})\n"))

        try:
            cuentas = list_accessible_ad_accounts()
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'❌ No se pudo listar cuentas: {exc}'))
            return

        if not cuentas:
            self.stdout.write(self.style.WARNING('No hay cuentas publicitarias accesibles.'))
            return

        total_anuncios = alertas = 0

        for cuenta in cuentas:
            act_id = cuenta.get('id')
            nombre_cuenta = cuenta.get('name') or act_id
            self.stdout.write(f"\n━━━ {nombre_cuenta}  ({act_id}, {cuenta.get('currency', '?')})")

            params = {
                'fields': f'id,name,effective_status,campaign{{name,effective_status}},'
                          f'creative{{{CREATIVE_FIELDS}}}',
                'limit': 100,
            }
            if solo_activos:
                params['effective_status'] = '["ACTIVE"]'

            try:
                anuncios = _paginar(f'/{act_id}/ads', params)
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f'   ⚠️  no se pudo leer: {exc}'))
                continue

            if not anuncios:
                self.stdout.write('   (sin anuncios en ese filtro)')
                continue

            for ad in anuncios:
                total_anuncios += 1
                urls = [u for u in _urls_en(ad.get('creative') or {}) if dominio in u.lower()]
                if not urls:
                    continue

                campana = (ad.get('campaign') or {}).get('name', '?')
                estado = ad.get('effective_status', '?')
                for url in sorted(set(urls)):
                    ruta = url.lower()
                    if RUTA_ROMANTICA in ruta:
                        alertas += 1
                        marca, estilo = '🚨 ROMÁNTICA', self.style.ERROR
                    elif RUTA_CELEBRACIONES in ruta:
                        marca, estilo = '✅ CELEBRACIONES', self.style.SUCCESS
                    else:
                        marca, estilo = '  ', self.style.NOTICE
                    self.stdout.write(estilo(
                        f'   {marca} [{estado}] {campana} › {ad.get("name", "?")}\n'
                        f'        {url}'))

        self.stdout.write('\n' + '─' * 60)
        self.stdout.write(f'Anuncios revisados: {total_anuncios}')
        if alertas:
            self.stdout.write(self.style.ERROR(
                f'🚨 {alertas} link(s) a {RUTA_ROMANTICA}/ — revisar si venden cumpleaños '
                f'o despedidas: esa landing ya solo ofrece la experiencia de pareja. '
                f'Si es el caso, apuntarlos a {RUTA_CELEBRACIONES}/.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'✅ Ningún anuncio apunta a {RUTA_ROMANTICA}/ — nada que corregir.'))
