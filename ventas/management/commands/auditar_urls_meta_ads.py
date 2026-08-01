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

Los BOOSTS de publicación son el caso difícil: su creativo suele traer solo un
`effective_object_story_id` y el destino real vive en el POST. Por eso, cuando el
creativo no revela ninguna URL, se resuelve también el post. Sin esto quedaba un
hueco: en la primera corrida (2026-07-31) 420 de 431 anuncios no exponían link.

Dos trampas ya resueltas acá:
  · Meta ENVUELVE los links (`l.facebook.com/l.php?u=<url-encodeada>`), así que
    todo texto se escanea además desencodeado — si no, el destino real sale
    ilegible o directamente no matchea.
  · Muchos anuncios comparten el mismo post → los posts se cachean por id, o
    serían cientos de llamadas repetidas.

Uso:
    python manage.py auditar_urls_meta_ads                  # solo anuncios ACTIVE
    python manage.py auditar_urls_meta_ads --todos          # incluye pausados
    python manage.py auditar_urls_meta_ads --rapido         # NO resuelve posts
    python manage.py auditar_urls_meta_ads --dominio otra.cl
"""
import re
from urllib.parse import unquote

from django.core.management.base import BaseCommand

from ventas.services.meta_reporter import (
    _get, get_page_access_token, list_accessible_ad_accounts,
)

# Campos del creativo donde Meta puede esconder el destino. Se piden todos y
# después se escanea el JSON completo: más barato que mantener rutas a mano.
# `object_url` es el destino de varios formatos viejos de boost y se lee con el
# mismo permiso de anuncios — o sea, gratis y sin depender de la API de Páginas.
CREATIVE_FIELDS = (
    'object_story_spec,asset_feed_spec,link_destination_display_url,'
    'template_url,url_tags,effective_object_story_id,object_url,object_type,name'
)

# El esquema es OPCIONAL a propósito: `link_destination_display_url` llega como
# "aremko.cl/celebraciones", sin http://. Esto también engancha ruido tipo
# "object_story_spec.link_data", pero es inofensivo: abajo solo se conservan las
# coincidencias que contienen el dominio vigilado.
RE_URL = re.compile(r'(?:https?://)?[\w.-]+\.[a-z]{2,}(?:/[^\s"\'<>\\),]*)?', re.IGNORECASE)

# Meta envuelve los destinos: l.facebook.com/l.php?u=<destino-encodeado>&h=<hash>.
# Se captura el destino y se consumen los params que le siguen; si no, el `&h=…`
# se pega al final de la URL desenvuelta. Sin esto el reporte muestra el
# envoltorio en vez del link real y cuenta la misma URL varias veces.
RE_SHIM = re.compile(
    r'https?://(?:l|lm|www)\.facebook\.com/l\.php\?u=([^&\s"\'<>]+)(?:&[^\s"\'<>]*)?',
    re.IGNORECASE)

# Rutas que este comando vigila (las dos puertas de H-087).
RUTA_ROMANTICA = '/experiencia-romantica'
RUTA_CELEBRACIONES = '/celebraciones'

# Campos del POST de una publicación impulsada. Se piden en dos tandas: si Meta
# rechaza los campos ricos (varía según tipo de post y permisos), se reintenta con
# el mínimo en vez de perder el anuncio entero.
STORY_FIELDS = 'permalink_url,message,attachments{url,unshimmed_url,target,subattachments}'
STORY_FIELDS_MINIMO = 'permalink_url,message'


def _urls_con_campo(nodo, ruta=''):
    """Pares (campo, url) — de DÓNDE salió cada URL, no solo cuál es.

    El campo importa para decidir si hay algo que arreglar: una URL en
    `message` es el PIE DE FOTO de la publicación (en Instagram el texto no es
    clickeable: nadie hace clic ahí), mientras que una en `attachments…url` sí
    es el destino real del anuncio. Sin esta distinción, "arreglar el link"
    podría terminar editando el texto de una publicación ya publicada.
    """
    hallados = []
    if isinstance(nodo, str):
        # Primero se desenvuelven los links de Meta (queda el destino real y ya
        # desencodeado), y recién ahí se buscan URLs.
        texto = RE_SHIM.sub(lambda m: unquote(m.group(1)), nodo)
        urls = list(RE_URL.findall(texto))
        plano = unquote(texto)
        if plano != texto:
            urls.extend(RE_URL.findall(plano))
        hallados.extend((ruta or '(raíz)', u) for u in urls)
    elif isinstance(nodo, dict):
        for clave, valor in nodo.items():
            hallados.extend(_urls_con_campo(valor, f'{ruta}.{clave}' if ruta else clave))
    elif isinstance(nodo, (list, tuple)):
        for i, valor in enumerate(nodo):
            hallados.extend(_urls_con_campo(valor, f'{ruta}[{i}]'))
    return hallados


def _urls_en(nodo):
    """Solo las URLs, sin el campo (se conserva por comodidad de los tests)."""
    return [u for _, u in _urls_con_campo(nodo)]


def es_clickeable(campo):
    """True si ese campo es un DESTINO del anuncio y no texto redactado.

    `message`/`caption`/`description` son texto que ve el usuario; el resto
    (link, url, website_url, unshimmed_url…) son destinos de verdad.
    """
    ultimo = campo.rsplit('.', 1)[-1].split('[')[0].lower()
    return ultimo not in ('message', 'caption', 'description', 'name', 'title')


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
        parser.add_argument('--rapido', action='store_true',
                            help='NO resuelve el post de los boosts (más rápido, pero deja huecos).')
        parser.add_argument('--dominio', default='aremko.cl',
                            help='Dominio a vigilar. Default: aremko.cl')

    # -- resolución de posts (boosts) -------------------------------------
    def _token_de_pagina(self, page_id):
        """Page Access Token de esa página, cacheado. None si no se puede.

        Los posts de una Página NO se leen con el token de sistema (devuelve
        error #10 pidiendo `pages_read_engagement`): hay que usar el token de la
        página, que el system user hereda si tiene acceso a ella.
        """
        if page_id in self._cache_tokens:
            return self._cache_tokens[page_id]
        try:
            token = get_page_access_token(page_id)
        except Exception:  # noqa: BLE001 — página ajena o sin permisos
            token = None
        self._cache_tokens[page_id] = token
        return token

    def _post(self, story_id):
        """Post de un boost, cacheado. Devuelve {} si no se pudo leer.

        Registra los fallos en vez de tragárselos: un post ilegible es un hueco
        en la auditoría y tiene que salir en el resumen, no desaparecer.
        """
        if story_id in self._cache_posts:
            return self._cache_posts[story_id]

        # El story_id es "{page_id}_{post_id}": de ahí sale a qué página pedirle
        # el token. Si no se consigue, se intenta igual con el de sistema.
        page_id = story_id.split('_')[0] if '_' in story_id else None
        token = self._token_de_pagina(page_id) if page_id else None

        post, ultimo_error = {}, 'sin intentos'
        for campos in (STORY_FIELDS, STORY_FIELDS_MINIMO):
            try:
                post = _get(f'/{story_id}', {'fields': campos}, token=token)
                break
            except Exception as exc:  # noqa: BLE001 — se reintenta y si no, se cuenta
                ultimo_error = str(exc)
        else:
            self._posts_ilegibles.append((story_id, ultimo_error))

        self._cache_posts[story_id] = post
        return post

    def handle(self, *args, **opts):
        dominio = opts['dominio'].lower()
        solo_activos = not opts['todos']
        resolver_posts = not opts['rapido']
        self._cache_posts = {}
        self._cache_tokens = {}
        self._posts_ilegibles = []
        self._posts_resueltos = 0

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
                creativo = ad.get('creative') or {}
                hallazgos = [(c, u) for c, u in _urls_con_campo(creativo)
                             if dominio in u.lower()]
                origen = 'creativo'

                # Boost sin link en el creativo → el destino vive en el POST.
                story_id = creativo.get('effective_object_story_id')
                if not hallazgos and resolver_posts and story_id:
                    post = self._post(story_id)
                    if post:
                        self._posts_resueltos += 1
                        hallazgos = [(c, u) for c, u in _urls_con_campo(post)
                                     if dominio in u.lower()]
                        origen = 'post'

                if not hallazgos:
                    continue

                campana = (ad.get('campaign') or {}).get('name', '?')
                estado = ad.get('effective_status', '?')
                # Una misma URL puede salir de varios campos: se queda el más
                # "fuerte" (un destino clickeable manda sobre el mismo link
                # mencionado de paso en el texto).
                por_url = {}
                for campo, url in hallazgos:
                    if url not in por_url or (es_clickeable(campo)
                                              and not es_clickeable(por_url[url])):
                        por_url[url] = campo

                for url, campo in sorted(por_url.items()):
                    ruta = url.lower()
                    clic = es_clickeable(campo)
                    if RUTA_ROMANTICA in ruta:
                        alertas += 1
                        marca, estilo = '🚨 ROMÁNTICA', self.style.ERROR
                    elif RUTA_CELEBRACIONES in ruta:
                        marca, estilo = '✅ CELEBRACIONES', self.style.SUCCESS
                    else:
                        marca, estilo = '  ', self.style.NOTICE
                    tipo = 'DESTINO' if clic else 'solo texto'
                    self.stdout.write(estilo(
                        f'   {marca} [{estado}] {campana} › {ad.get("name", "?")}\n'
                        f'        {url}\n'
                        f'        ↳ {tipo} · {origen}.{campo} · ad {ad.get("id", "?")}'))

        self.stdout.write('\n' + '─' * 60)
        self.stdout.write(f'Anuncios revisados: {total_anuncios}')

        # Cobertura: sin esto, "no encontré nada" se confunde con "no pude mirar".
        if resolver_posts:
            self.stdout.write(
                f'Publicaciones impulsadas resueltas: {self._posts_resueltos} '
                f'({len(self._cache_posts)} posts únicos consultados)')
            if self._posts_ilegibles:
                self.stdout.write(self.style.WARNING(
                    f'⚠️  {len(self._posts_ilegibles)} post(s) NO se pudieron leer — '
                    f'ahí queda un hueco en la auditoría. Motivos:'))
                # Agrupado por causa: 300 líneas del mismo error no dicen más que una.
                por_causa = {}
                for story_id, error in self._posts_ilegibles:
                    causa = error[:110]
                    por_causa.setdefault(causa, []).append(story_id)
                for causa, ids in sorted(por_causa.items(), key=lambda x: -len(x[1])):
                    self.stdout.write(f'     [{len(ids)}] {causa}')
                    self.stdout.write(f'          ej: {ids[0]}')
                if any('pages_read_engagement' in c or 'Page Public Content' in c
                       for c in por_causa):
                    self.stdout.write(self.style.WARNING(
                        '     → Falta permiso de LECTURA DE PÁGINA para el system user. '
                        'Se arregla en Business Manager (Configuración → Usuarios del '
                        'sistema → asignar la Página con acceso de Contenido), no en código.'))
        else:
            self.stdout.write(self.style.WARNING(
                '⚠️  Modo --rapido: NO se resolvieron los posts de los boosts, '
                'así que un destino escondido en la publicación no se vería.'))

        if alertas:
            self.stdout.write(self.style.ERROR(
                f'🚨 {alertas} link(s) a {RUTA_ROMANTICA}/ — revisar si venden cumpleaños '
                f'o despedidas: esa landing ya solo ofrece la experiencia de pareja. '
                f'Si es el caso, apuntarlos a {RUTA_CELEBRACIONES}/.'))
        elif resolver_posts and not self._posts_ilegibles:
            self.stdout.write(self.style.SUCCESS(
                f'✅ Ningún anuncio apunta a {RUTA_ROMANTICA}/ — creativos Y publicaciones '
                f'impulsadas revisados, sin huecos.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'✅ Ningún anuncio apunta a {RUTA_ROMANTICA}/ entre los que se pudieron leer.'))
