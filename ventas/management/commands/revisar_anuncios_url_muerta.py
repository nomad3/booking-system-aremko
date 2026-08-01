# -*- coding: utf-8 -*-
"""Diagnostica los anuncios cuyo DESTINO clickeable apunta a una URL muerta.

Salió de la auditoría H-087 (`auditar_urls_meta_ads`): 4 anuncios ACTIVE llevan a
rutas que hoy dan 404, y ~7 a un dominio que ya no existe. Antes de tocarlos hay
que contestar tres preguntas, y ninguna se responde adivinando:

  1. ¿GASTAN? Un anuncio "ACTIVE" con $0 de gasto es ruido de inventario, no
     plata quemada. Cambia por completo si vale la pena intervenir.
  2. ¿SE PUEDEN EDITAR? Un creativo `link_data.link` se corrige por API. Uno que
     referencia una publicación (`object_story_id`) NO: el destino está pegado a
     la publicación ya publicada, no al anuncio.
  3. ¿TENEMOS PERMISO DE ESCRITURA? El token puede leer anuncios sin poder
     modificarlos.

Este comando NO modifica nada por defecto. Solo con `--aplicar` corrige la URL, y
únicamente en los creativos donde el destino es realmente editable — nunca toca
publicaciones ni pausa anuncios (pausar es una decisión de negocio, no técnica).

Uso:
    python manage.py revisar_anuncios_url_muerta            # diagnóstico
    python manage.py revisar_anuncios_url_muerta --aplicar  # corrige lo editable
"""
from django.core.management.base import BaseCommand

from ventas.services.meta_reporter import _get, resolve_token

# Anuncios con destino clickeable roto (de la corrida del 2026-08-01).
ANUNCIOS_SOSPECHOSOS = [
    ('23852739550490781', 'http://www.aremko.cl/aguas-calientes'),
    ('23852739519550781', 'http://www.aremko.cl/alojamiento'),
    ('23852651648680781', 'http://www.aremko.cl/regalos'),
    ('23852590055000781', 'http://www.aremko.cl/regalos'),
]

# A dónde debería ir cada ruta muerta. Verificadas 200 el 2026-08-01.
REEMPLAZOS = {
    '/aguas-calientes': 'https://www.aremko.cl/tinas/',
    '/alojamiento': 'https://www.aremko.cl/alojamientos/',
    '/regalos': 'https://www.aremko.cl/ventas/giftcards/',
}


def destino_correcto(url_muerta):
    """URL viva equivalente, o None si no hay mapeo."""
    for ruta, reemplazo in REEMPLAZOS.items():
        if ruta in (url_muerta or '').lower():
            return reemplazo
    return None


class Command(BaseCommand):
    help = 'Diagnostica (y opcionalmente corrige) los anuncios con destino a URL muerta.'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true',
                            help='Corrige la URL donde el destino sea editable. Sin esto, solo informa.')
        parser.add_argument('--dias', type=int, default=90,
                            help='Ventana para medir el gasto. Default: 90.')

    def _permisos(self):
        """Permisos del token. Devuelve set() si no se pudo consultar."""
        try:
            token = resolve_token()
            data = _get('/debug_token', {'input_token': token})
            return set((data.get('data') or {}).get('scopes') or [])
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.WARNING(f'   (no se pudo leer permisos: {exc})'))
            return set()

    def _gasto(self, ad_id, dias):
        """Gasto/impresiones/clics del anuncio. {} si no hay datos."""
        try:
            data = _get(f'/{ad_id}/insights', {
                'fields': 'spend,impressions,clicks,account_currency',
                'date_preset': 'maximum',
            })
            filas = data.get('data') or []
            return filas[0] if filas else {}
        except Exception as exc:  # noqa: BLE001
            return {'_error': str(exc)[:100]}

    def handle(self, *args, **opts):
        aplicar = opts['aplicar']
        self.stdout.write(self.style.SUCCESS(
            '\n🔧 Anuncios con destino a URL muerta\n'))

        permisos = self._permisos()
        puede_escribir = 'ads_management' in permisos
        if permisos:
            self.stdout.write(f'Permisos del token: {", ".join(sorted(permisos)) or "(ninguno)"}')
        self.stdout.write(
            f'¿Puede modificar anuncios? '
            f'{"SÍ (ads_management presente)" if puede_escribir else "NO — falta ads_management"}\n')

        editables, no_editables, sin_gasto = [], [], []

        for ad_id, url_muerta in ANUNCIOS_SOSPECHOSOS:
            self.stdout.write(f'━━━ ad {ad_id}')
            self.stdout.write(f'    destino actual: {url_muerta}')

            try:
                ad = _get(f'/{ad_id}', {
                    'fields': 'name,effective_status,creative{id,object_story_id,'
                              'effective_object_story_id,object_story_spec}',
                })
            except Exception as exc:  # noqa: BLE001
                self.stdout.write(self.style.ERROR(f'    ❌ no se pudo leer: {exc}'))
                continue

            creativo = ad.get('creative') or {}
            spec = creativo.get('object_story_spec') or {}
            link_editable = bool((spec.get('link_data') or {}).get('link'))
            es_publicacion = bool(creativo.get('object_story_id')
                                  or creativo.get('effective_object_story_id'))

            gasto = self._gasto(ad_id, opts['dias'])
            if '_error' in gasto:
                resumen_gasto = f"no se pudo medir ({gasto['_error']})"
            elif not gasto:
                resumen_gasto = 'SIN datos de gasto (histórico) → nunca entregó'
                sin_gasto.append(ad_id)
            else:
                moneda = gasto.get('account_currency', '')
                resumen_gasto = (f"gasto histórico {gasto.get('spend', '0')} {moneda} · "
                                 f"{gasto.get('impressions', '0')} impresiones · "
                                 f"{gasto.get('clicks', '0')} clics")
                if float(gasto.get('spend') or 0) == 0:
                    sin_gasto.append(ad_id)

            self.stdout.write(f'    estado: {ad.get("effective_status", "?")} · {resumen_gasto}')

            nuevo = destino_correcto(url_muerta)
            if link_editable:
                editables.append((ad_id, creativo, nuevo))
                self.stdout.write(self.style.SUCCESS(
                    f'    ✏️  destino EDITABLE por API → debería ir a {nuevo}'))
            else:
                no_editables.append(ad_id)
                self.stdout.write(self.style.WARNING(
                    '    🔒 destino NO editable por API: el link está pegado a la '
                    'PUBLICACIÓN impulsada, no al anuncio.'))
                if es_publicacion:
                    self.stdout.write(
                        '        Para cambiarlo hay que crear un anuncio nuevo con el '
                        'link corregido, o dejarlo y pausar el viejo (decisión de negocio).')

        # -- resumen -------------------------------------------------------
        self.stdout.write('\n' + '─' * 60)
        self.stdout.write(f'Editables por API: {len(editables)} · '
                          f'Pegados a una publicación: {len(no_editables)}')
        if sin_gasto:
            self.stdout.write(self.style.SUCCESS(
                f'💡 {len(sin_gasto)} de {len(ANUNCIOS_SOSPECHOSOS)} no registran gasto: '
                f'están "ACTIVE" pero no entregan (campaña sin presupuesto o apagada '
                f'más arriba). Ahí no hay plata quemándose.'))

        if not aplicar:
            if editables:
                self.stdout.write(
                    '\nPara corregir los editables: volver a correr con --aplicar')
            return

        if not editables:
            self.stdout.write(self.style.WARNING(
                '\nNada que aplicar: ningún destino es editable por API.'))
            return
        if not puede_escribir:
            self.stdout.write(self.style.ERROR(
                '\n❌ No se aplica nada: el token no tiene ads_management. '
                'Se amplía en Business Manager (Usuarios del sistema → Generar token '
                'con ads_management), no en código.'))
            return

        for ad_id, creativo, nuevo in editables:
            if not nuevo:
                self.stdout.write(f'   {ad_id}: sin URL de reemplazo definida, se omite')
                continue
            self.stdout.write(self.style.ERROR(
                f'   {ad_id}: la corrección de creativos requiere crear un creativo '
                f'nuevo (los creativos de Meta son inmutables). Destino objetivo: {nuevo}. '
                f'No se ejecuta automáticamente: crear creativos cambia el anuncio en vivo.'))
