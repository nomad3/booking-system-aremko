# -*- coding: utf-8 -*-
"""El resumen, en texto y en HTML para el correo.

Restricción de diseño: leerlo completo en el teléfono tiene que tomar 30
segundos. Todo lo que no ayude a decidir algo hoy, sobra.
"""
from .alertas import ALTA

MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
DIAS = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado',
        'domingo')

NEGOCIOS_SECUNDARIOS = (('datamatic', 'Datamatic'), ('torqueria', 'Torquería'))

# El correo es la foto del amanecer; el panel es donde se vive el día. El
# link va arriba porque abajo nadie llega.
URL_PANEL = 'https://www.aremko.cl/sala/'


def clp(n):
    if n is None:
        return '—'
    return '$' + format(int(round(n)), ',d').replace(',', '.')


def compacto(n):
    """$18,4M — para que la foto quepa en el ancho de un teléfono."""
    if n is None:
        return '—'
    n = float(n)
    if abs(n) >= 1_000_000:
        return f'${n / 1_000_000:.1f}M'.replace('.', ',')
    if abs(n) >= 1_000:
        return f'${n / 1_000:.0f}k'
    return clp(n)


def pct(valor):
    """▲ +9% / ▼ −3% / — cuando no hay con qué comparar."""
    if valor is None or not isinstance(valor, (int, float)):
        return '—'
    flecha = '▲' if valor > 0 else ('▼' if valor < 0 else '·')
    signo = '+' if valor > 0 else ''
    return f'{flecha} {signo}{valor:.0f}%'.replace('-', '−')


# Palabras de enlace que, colgando al final de un recorte, se leen como un
# error de tipeo: «…entra el banco, la…». Se sueltan junto con el corte.
_PALABRAS_COLGANTES = {
    'a', 'al', 'ante', 'con', 'contra', 'de', 'del', 'desde', 'e', 'el', 'en',
    'entre', 'esa', 'ese', 'esta', 'este', 'hacia', 'hasta', 'la', 'las', 'lo',
    'los', 'mi', 'o', 'para', 'por', 'que', 'se', 'si', 'sin', 'sobre', 'su',
    'sus', 'tras', 'tu', 'un', 'una', 'unos', 'unas', 'y',
}


def recortar(texto, tope):
    """Corta en la última palabra completa, no a la mitad de una.

    «Catorce en tierra. En esos catorce entra el banco, la fa» se lee como un
    error de tipeo; con puntos suspensivos se lee como lo que es: un texto más
    largo. Y si al cortar queda colgando un artículo («…el banco, la…»),
    también se suelta: es ruido que no aporta nada.
    """
    texto = (texto or '').strip()
    if len(texto) <= tope:
        return texto

    palabras = texto[:tope].rsplit(' ', 1)[0].split()
    while (len(palabras) > 1 and
           palabras[-1].strip(',.;:—-').lower() in _PALABRAS_COLGANTES):
        palabras.pop()
    cortado = ' '.join(palabras).rstrip(' ,.;:—-')
    return (cortado or texto[:tope].rstrip()) + '…'


def fecha_larga(f):
    return f'{DIAS[f.weekday()]} {f.day} de {MESES[f.month - 1]}'


def _filas_foto(datos):
    """(etiqueta, valor, variación) de la foto del mes. Lista, no HTML: así
    el mismo cálculo alimenta el texto plano y el correo."""
    filas = []
    tot = (datos.get('comparativa') or {}).get('totales') or {}
    filas.append(('Ventas del mes', compacto(tot.get('facturado_actual')),
                  pct(tot.get('facturado_pct_cambio'))))
    filas.append(('Reservas', str(tot.get('reservas_actual', '—')),
                  pct(tot.get('reservas_pct_cambio'))))

    ads = datos.get('ads') or {}
    detalle = []
    if ads.get('meta') is not None:
        detalle.append(f'Meta {compacto(ads["meta"])}')
    if ads.get('google') is not None:
        detalle.append(f'Google {compacto(ads["google"])}')
    filas.append(('Gasto en Ads', compacto(datos.get('gasto_ads')),
                  ' + '.join(detalle) or '—'))

    caja = datos.get('caja') or {}
    nota_caja = ''
    if caja.get('sin_ancla'):
        nota_caja = f'sin {len(caja["sin_ancla"])} cuenta(s)'
    filas.append(('Caja Aremko', compacto(datos.get('caja_total')), nota_caja))

    colchon = datos.get('colchon_dias')
    filas.append(('Colchón', f'{colchon} días' if colchon is not None else '—',
                  'al ritmo de gastos de los últimos 28 días'))
    return filas


def a_texto(datos):
    """Versión en texto plano (cuerpo del correo y salida del --dry-run)."""
    L = []
    L.append(f'AREMKO · {fecha_larga(datos["fecha"])}')
    L.append(f'Panel del día: {URL_PANEL}')
    L.append('')

    L.append('TUS PRIORIDADES DE LA SEMANA')
    if datos['prioridades']:
        for p in datos['prioridades']:
            marca = f'[{p.get_negocio_display()}] ' if p.negocio != 'aremko' else ''
            L.append(f'  {p.orden}. {marca}{p.texto}')
    elif datos['sin_prioridades']:
        L.append('  (no fijaste prioridades esta semana)')
    else:
        L.append('  ✓ todas listas')
    L.append('')

    ref = (datos.get('comparativa') or {}).get('rango_anterior') or 'mes anterior'
    L.append(f'LA FOTO  (vs {ref})')
    for etiqueta, valor, extra in _filas_foto(datos):
        L.append(f'  {etiqueta:<16} {valor:>8}   {extra}')
    L.append('')

    if datos['alertas']:
        L.append(f'ATENCIÓN HOY ({len(datos["alertas"])})')
        for a in datos['alertas']:
            marca = '!!' if a['nivel'] == ALTA else ' ·'
            L.append(f'  {marca} {a["texto"]}')
            if a['accion']:
                L.append(f'       → {a["accion"]}')
    else:
        L.append('ATENCIÓN HOY — nada fuera de rango')
    L.append('')

    L.append('PUBLICACIONES DE HOY')
    if datos['publicaciones']:
        for p in datos['publicaciones']:
            estado = '✓' if p.get('estado') == 'publicada' else '·'
            hora = p.get('hora') or '--:--'
            L.append(f'  {estado} {hora} {p.get("canal", "")}: '
                     f'{recortar(p.get("titulo"), 70)}')
        sem = (datos.get('telar') or {}).get('semana') or {}
        if sem:
            L.append(f'  Semana: {sem.get("publicadas")}/{sem.get("total")} '
                     f'publicadas · {sem.get("por_publicar")} por publicar')
    elif datos['telar'] is None:
        L.append('  (el Telar no respondió)')
    else:
        L.append('  Nada programado para hoy')
    L.append('')

    if datos.get('presencia_web'):
        ga4 = datos['presencia_web'].get('ga4')
        gsc = datos['presencia_web'].get('gsc')
        L.append('PRESENCIA WEB (lunes)')
        if ga4:
            L.append(f'  Sesiones 7d: {ga4.sessions} · '
                     f'Clics WhatsApp: {ga4.whatsapp_clicks} '
                     f'(al {ga4.fecha_snapshot:%d-%m})')
        if gsc:
            L.append(f'  Google: {gsc.clicks} clics · {gsc.impressions} '
                     f'impresiones · posición {gsc.position:.1f}')
        L.append('')

    notas = datos.get('notas') or {}
    lineas_neg = []
    for clave, nombre in NEGOCIOS_SECUNDARIOS:
        n = notas.get(clave)
        if n:
            lineas_neg.append(f'  {nombre}: {n.texto} '
                              f'(al {n.actualizada:%d-%m})')
        else:
            lineas_neg.append(f'  {nombre}: sin nota')
    L.append('OTROS NEGOCIOS')
    L.extend(lineas_neg)
    L.append('')

    caja = datos.get('caja') or {}
    coberturas = []
    for c in caja.get('cuentas') or []:
        if c.get('ultima_cartola'):
            coberturas.append(f'{c["nombre"]} al {c["ultima_cartola"]:%d-%m}')
    if coberturas:
        L.append('Cobertura de los datos: ' + ' · '.join(coberturas))
    return '\n'.join(L)


# ── HTML ─────────────────────────────────────────────────────────────────

_CSS_SEC = ('margin:22px 0 8px;font:600 12px/1.3 -apple-system,Segoe UI,Roboto,'
            'sans-serif;letter-spacing:.08em;text-transform:uppercase;'
            'color:#8a8578')
_CSS_TXT = ('font:400 15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;'
            'color:#2f2c26')


def _esc(t):
    return (str(t).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;'))


def a_html(datos):
    h = []
    h.append('<div style="max-width:600px;margin:0 auto;padding:20px 18px;'
             'background:#fbfaf7;">')
    h.append(f'<div style="{_CSS_TXT};font-size:20px;font-weight:600;">'
             f'Aremko</div>')
    h.append(f'<div style="{_CSS_TXT};color:#8a8578;font-size:14px;">'
             f'{_esc(fecha_larga(datos["fecha"]))}</div>')
    h.append(f'<div style="{_CSS_TXT};margin-top:10px;"><a href="{URL_PANEL}" '
             f'style="display:inline-block;padding:9px 16px;background:#2f2c26;'
             f'color:#fbfaf7;text-decoration:none;border-radius:8px;'
             f'font-size:14px;font-weight:600;">Abrir el panel del día →</a></div>')

    # Prioridades
    h.append(f'<div style="{_CSS_SEC}">Tus prioridades de la semana</div>')
    if datos['prioridades']:
        h.append(f'<ol style="{_CSS_TXT};margin:0;padding-left:20px;">')
        for p in datos['prioridades']:
            marca = (f'<b>[{_esc(p.get_negocio_display())}]</b> '
                     if p.negocio != 'aremko' else '')
            h.append(f'<li style="margin:4px 0;">{marca}{_esc(p.texto)}</li>')
        h.append('</ol>')
    else:
        texto = ('No fijaste prioridades esta semana.'
                 if datos['sin_prioridades'] else '✓ Todas listas.')
        h.append(f'<div style="{_CSS_TXT};color:#8a8578;">{texto}</div>')

    # La foto
    ref = (datos.get('comparativa') or {}).get('rango_anterior') or ''
    h.append(f'<div style="{_CSS_SEC}">La foto'
             f'{f" · vs {_esc(ref)}" if ref else ""}</div>')
    h.append('<table style="width:100%;border-collapse:collapse;">')
    for etiqueta, valor, extra in _filas_foto(datos):
        h.append(
            f'<tr>'
            f'<td style="{_CSS_TXT};padding:7px 0;border-bottom:1px solid #ece8e0;">'
            f'{_esc(etiqueta)}</td>'
            f'<td style="{_CSS_TXT};padding:7px 0;border-bottom:1px solid #ece8e0;'
            f'text-align:right;font-weight:600;font-variant-numeric:tabular-nums;">'
            f'{_esc(valor)}</td>'
            f'<td style="{_CSS_TXT};padding:7px 0 7px 12px;'
            f'border-bottom:1px solid #ece8e0;font-size:13px;color:#8a8578;'
            f'text-align:right;">{_esc(extra)}</td>'
            f'</tr>')
    h.append('</table>')

    # Alertas
    n = len(datos['alertas'])
    h.append(f'<div style="{_CSS_SEC}">'
             f'{f"Atención hoy ({n})" if n else "Atención hoy"}</div>')
    if datos['alertas']:
        for a in datos['alertas']:
            color = '#a33b2a' if a['nivel'] == ALTA else '#8a6d3b'
            h.append(
                f'<div style="{_CSS_TXT};padding:9px 12px;margin:6px 0;'
                f'background:#fff;border-left:3px solid {color};">'
                f'<div style="font-weight:600;color:{color};">'
                f'{_esc(a["texto"])}</div>'
                + (f'<div style="font-size:13px;color:#8a8578;margin-top:2px;">'
                   f'{_esc(a["accion"])}</div>' if a['accion'] else '')
                + '</div>')
    else:
        h.append(f'<div style="{_CSS_TXT};color:#5b7a52;">'
                 f'Nada fuera de rango.</div>')

    # Publicaciones
    h.append(f'<div style="{_CSS_SEC}">Publicaciones de hoy</div>')
    if datos['publicaciones']:
        h.append(f'<div style="{_CSS_TXT}">')
        for p in datos['publicaciones']:
            publicada = p.get('estado') == 'publicada'
            icono = '✓' if publicada else '○'
            color = '#8a8578' if publicada else '#2f2c26'
            h.append(
                f'<div style="padding:5px 0;color:{color};">'
                f'{icono} <b>{_esc(p.get("hora") or "--:--")}</b> '
                f'{_esc(p.get("canal", ""))} — '
                f'{_esc(recortar(p.get("titulo"), 80))}</div>')
        sem = (datos.get('telar') or {}).get('semana') or {}
        if sem:
            h.append(f'<div style="font-size:13px;color:#8a8578;margin-top:6px;">'
                     f'Semana: {sem.get("publicadas")}/{sem.get("total")} '
                     f'publicadas · {sem.get("por_publicar")} por publicar</div>')
        h.append('</div>')
    else:
        texto = ('El Telar no respondió.' if datos['telar'] is None
                 else 'Nada programado para hoy.')
        h.append(f'<div style="{_CSS_TXT};color:#8a8578;">{texto}</div>')

    # Presencia web (lunes)
    if datos.get('presencia_web'):
        ga4 = datos['presencia_web'].get('ga4')
        gsc = datos['presencia_web'].get('gsc')
        h.append(f'<div style="{_CSS_SEC}">Presencia web</div>')
        h.append(f'<div style="{_CSS_TXT}">')
        if ga4:
            h.append(f'<div>Sesiones 7d: <b>{ga4.sessions}</b> · '
                     f'clics a WhatsApp: <b>{ga4.whatsapp_clicks}</b> '
                     f'<span style="color:#8a8578;font-size:13px;">'
                     f'(al {ga4.fecha_snapshot:%d-%m})</span></div>')
        if gsc:
            h.append(f'<div>Google: <b>{gsc.clicks}</b> clics · '
                     f'{gsc.impressions} impresiones · '
                     f'posición {gsc.position:.1f}</div>')
        h.append('</div>')

    # Otros negocios
    notas = datos.get('notas') or {}
    h.append(f'<div style="{_CSS_SEC}">Otros negocios</div>')
    h.append(f'<div style="{_CSS_TXT}">')
    for clave, nombre in NEGOCIOS_SECUNDARIOS:
        nota = notas.get(clave)
        if nota:
            h.append(f'<div style="padding:3px 0;"><b>{nombre}:</b> '
                     f'{_esc(nota.texto)} '
                     f'<span style="color:#8a8578;font-size:13px;">'
                     f'(al {nota.actualizada:%d-%m})</span></div>')
        else:
            h.append(f'<div style="padding:3px 0;color:#8a8578;">'
                     f'<b>{nombre}:</b> sin nota</div>')
    h.append('</div>')

    # Cobertura
    caja = datos.get('caja') or {}
    coberturas = [f'{c["nombre"]} al {c["ultima_cartola"]:%d-%m}'
                  for c in (caja.get('cuentas') or [])
                  if c.get('ultima_cartola')]
    if coberturas:
        h.append(f'<div style="margin-top:22px;padding-top:12px;'
                 f'border-top:1px solid #ece8e0;font:400 12px/1.5 '
                 f'-apple-system,sans-serif;color:#a09a8c;">'
                 f'Cobertura de los datos: {_esc(" · ".join(coberturas))}</div>')

    h.append('</div>')
    return '\n'.join(h)
