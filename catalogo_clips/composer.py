"""Compositor de historias (H-071 B2-A) — receta → URL Cloudinary.

Filosofía M17: el server arma la RECETA (foto, texto, posición, preset) y
Cloudinary pinta los píxeles vía transformaciones encadenadas en la URL.
El preview ES la URL final → lo que se ve es exactamente el JPG que se descarga.
Cero CPU nuestra, cero timeout, cero infra nueva (mismo patrón que los
fotogramas de H-065).

Formato: historia Instagram 1080×1920 (9:16), texto dentro de la zona segura
(IG reserva ~250px arriba y ~320px abajo para username/botones).
"""
from urllib.parse import quote

# Lienzo historia
ANCHO, ALTO = 1080, 1920
BASE = f'c_fill,g_auto,w_{ANCHO},h_{ALTO}'

# Tipografía de marca real de Aremko para las historias (decisión de Jorge,
# 2026-07-20 — ver skill local historia-aremko/SKILL.md): "Glacial
# Indifference", peso NORMAL/regular, SIN negrita. Licencia SIL Open Font
# License (libre uso comercial). NO es una Google Font — Cloudinary no la
# sirve por nombre; hay que subir el .otf como recurso raw/authenticated
# (una sola vez: `python manage.py subir_fuente_historias`, en Render — ver
# ese comando) y referenciarla por su public_id CON extensión. Reemplaza
# "Montserrat" (elegida solo por ser segura en Cloudinary, no la de marca —
# Jorge, 2026-07-26: "el tipo de letra... no es la que se muestra").
FUENTE = 'GlacialIndifference-Regular.otf'

# Sello de marca en NEGRITA real (Jorge, 2026-07-26: "poco protagonismo" del
# sello contra fotos de tonos cálidos). Cloudinary NO sintetiza negrita sobre
# fuentes personalizadas subidas (verificado empíricamente: el modificador
# "_bold_" no produjo ningún cambio de píxeles contra este mismo archivo) —
# por eso se sube un SEGUNDO recurso, el .otf Bold real de la misma familia
# (mismo autor/licencia SIL OFL; mismo comando `subir_fuente_historias`,
# mismo public_id CON extensión). El cuerpo del texto principal sigue en
# FUENTE (regular) — Jorge, 2026-07-20: "peso regular, sin negrita" — el
# Bold es SOLO para este sello fijo, no para lo que redacta el operador.
FUENTE_SELLO = 'GlacialIndifference-Bold.otf'

# LIMITACIÓN CONOCIDA (Jorge, 2026-07-26): esta fuente NO tiene los glyphs ¿
# (U+00BF) ni ¡ (U+00A1) — se confirmó vía fontTools que es la ÚNICA versión
# que existe (2015, Hanken Design Co., 183/188 glyphs en todos los mirrors
# revisados) y que nunca se amplió. Decisión de Jorge: NO se resuelve en
# código (ni sustitución de glyph ni aviso automático) — quien redacte la
# historia simplemente evita el signo de apertura ¿/¡ (uso común igual en
# redes sociales). Si aparece un ¿/¡ roto en una imagen ya compuesta, se
# corrige el texto en el composer y se regenera. El Bold (arriba) tiene el
# MISMO hueco (verificado con fontTools al bajarlo) — esperable en la misma
# familia, no una sorpresa.

# Presets boutique (Angélica ELIGE, no diseña): colores de marca Aremko.
# 'velo'        = texto crema sobre velo oscuro cálido (fotos luminosas/día).
# 'crema'       = caja crema con texto verde bosque (fotos oscuras/noche).
# 'transparente'= sin caja, texto directo sobre la foto (Jorge, 2026-07-26,
#                 a partir de un ejemplo real sin caja que le gustó). Sin
#                 'caja' no hay contraste garantizado como en los otros 2 —
#                 por eso lleva 'sombra': True (e_shadow, ver _capas_linea),
#                 verificado empíricamente que SÍ se nota contra fondos
#                 ocupados (no es un no-op de Cloudinary).
PRESETS = {
    'velo': {'texto': 'F2E8D8', 'caja': '1E191299', 'sello': 'F2E8D8'},
    'crema': {'texto': '1E4438', 'caja': 'F2E8D8E0', 'sello': 'F2E8D8'},
    'transparente': {'texto': 'FFFFFF', 'caja': None, 'sello': 'F2E8D8', 'sombra': True},
}
PRESET_DEFAULT = 'velo'

# Tamaños para el modo "3 líneas" (Jorge, 2026-07-26: precio grande + resto
# chico, como una plantilla real que nos gustó). Cada tamaño distinto es su
# PROPIA capa l_text en Cloudinary (no existe "un tamaño por palabra" dentro
# de una sola capa) — por eso el alto de bloque de cada línea importa para
# apilarlas sin que se superpongan; _ALTURA_LINEA es el multiplicador
# tamaño→alto verificado empíricamente contra el cloud real (a 58/76/108px
# el bloque renderizado mide ≈1.35× el tamaño de fuente).
TAMANOS = {'chico': 36, 'normal': 58, 'grande': 80}
TAMANO_DEFAULT = 'normal'
MAX_LINEAS = 3
_ALTURA_LINEA = 1.35

# Posición del texto (gravity + offset) respetando la zona segura de IG.
POSICIONES = {
    'arriba': 'g_north,y_300',
    'centro': 'g_center,y_0',
    'abajo': 'g_south,y_380',
}
POSICION_DEFAULT = 'abajo'

# Sello de marca, siempre abajo (dentro de la zona segura).
# El separador es "•" (bullet, U+2022) — NO "·" (punto medio, U+00B7): Jorge
# reportó un "signo extraño" en prod (2026-07-26) y se confirmó con fontTools
# que Glacial Indifference NO tiene el punto medio (misma familia de huecos
# que ¿/¡, ver más arriba) — a diferencia de esos, este separador sale en el
# 100% de las historias, así que se corrige acá en vez de dejarlo a criterio
# de quien redacta. El bullet SÍ existe en la fuente.
SELLO_TEXTO = 'AREMKO • AGUAS CALIENTES JUNTO AL RÍO'


def _txt(texto):
    """Texto → doble URL-encoding (lo exige Cloudinary para , / % en l_text)."""
    return quote(quote(texto, safe=''), safe='')


def _cap(texto, maximo=220):
    """El texto de una historia es corto por diseño (y la URL, finita).

    Preserva saltos de línea explícitos que la operadora haya escrito
    (Jorge, 2026-07-26: antes `' '.join(texto.split())` colapsaba TODO —
    incluidos los `\\n` intencionales — a un solo párrafo corrido). Solo
    limpia espacios/tabs repetidos DENTRO de cada línea; `_txt()` ya sabe
    encodear el salto de línea para que Cloudinary lo respete (verificado
    empíricamente: %250A entre líneas renderiza como líneas separadas)."""
    lineas = [' '.join(linea.split()) for linea in (texto or '').splitlines()]
    return '\n'.join(lineas).strip()[:maximo]


def _cap_linea(texto, maximo=50):
    """Una de las 3 líneas con tamaño propio: cada una es su PROPIA capa
    Cloudinary (no un párrafo), así que no preserva `\\n` interno como
    `_cap` — solo limpia espacios repetidos y acota el largo (una línea
    corta, sobre todo si va en tamaño 'grande')."""
    return ' '.join((texto or '').split())[:maximo]


def lineas_normalizadas(lineas):
    """Hasta `MAX_LINEAS` {texto, tamano} — descarta líneas vacías; un
    tamaño fuera de `TAMANOS` degrada a 'normal' (nunca descarta la línea
    completa por eso, a diferencia de un texto vacío)."""
    out = []
    for l in (lineas or [])[:MAX_LINEAS]:
        if not isinstance(l, dict):
            continue
        texto = _cap_linea(l.get('texto', ''))
        if not texto:
            continue
        tamano = l.get('tamano') if l.get('tamano') in TAMANOS else TAMANO_DEFAULT
        out.append({'texto': texto, 'tamano': tamano})
    return out


def receta_normalizada(texto, posicion=None, preset=None, lineas=None):
    """Valida/normaliza la receta (lista blanca — nunca inyectar al URL directo).

    `lineas` (opcional, hasta 3 `{texto, tamano}`) es el modo "tamaños
    distintos por línea" (Jorge, 2026-07-26) — cuando viene con contenido,
    `url_historia` la usa EN VEZ de `texto` (que igual se guarda/normaliza,
    de modo que una receta vieja sin `lineas` siga renderizando idéntico:
    un solo bloque a tamaño normal, con sus saltos de línea preservados)."""
    return {
        'texto': _cap(texto),
        'posicion': posicion if posicion in POSICIONES else POSICION_DEFAULT,
        'preset': preset if preset in PRESETS else PRESET_DEFAULT,
        'lineas': lineas_normalizadas(lineas),
    }


def _alto(tamano):
    return TAMANOS.get(tamano, TAMANOS[TAMANO_DEFAULT]) * _ALTURA_LINEA


def _offsets_abajo(alturas, base=380):
    """Ancla g_south: la ÚLTIMA línea (más abajo) usa `base`; cada línea
    hacia arriba suma el alto de TODAS las que quedan debajo — verificado
    contra un render real de 3 líneas antes de fijar esta fórmula."""
    n = len(alturas)
    sufijo = [0.0] * n
    acumulado = 0.0
    for i in range(n - 1, -1, -1):
        sufijo[i] = acumulado
        acumulado += alturas[i]
    return [round(base + s) for s in sufijo]


def _offsets_arriba(alturas, base=300):
    """Ancla g_north: la PRIMERA línea usa `base`; cada línea hacia abajo
    suma el alto de todas las anteriores (espejo de `_offsets_abajo`)."""
    offsets = []
    acumulado = 0.0
    for alto in alturas:
        offsets.append(round(base + acumulado))
        acumulado += alto
    return offsets


def _offsets_centro(alturas):
    """Ancla g_center: el BLOQUE completo queda centrado en y=0; cada línea
    usa el punto medio de su propia franja dentro del bloque total."""
    total = sum(alturas)
    offsets = []
    acumulado = 0.0
    for alto in alturas:
        offsets.append(round(-total / 2 + acumulado + alto / 2))
        acumulado += alto
    return offsets


_GRAVEDAD = {'arriba': 'g_north', 'centro': 'g_center', 'abajo': 'g_south'}


def _capas_linea(texto, tamano_px, y, gravedad, preset, ancho=860):
    """Componentes Cloudinary de UNA línea (l_text[/e_shadow]/fl_layer_apply)."""
    partes = [f"l_text:{FUENTE}_{tamano_px}_center:{_txt(texto)}", f"co_rgb:{preset['texto']}"]
    if preset.get('caja'):
        partes.append(f"b_rgb:{preset['caja']}")
    partes.append(f"c_fit,w_{ancho}")
    salida = [','.join(partes)]
    if preset.get('sombra'):
        # Sombra sutil de legibilidad para presets sin caja (ver PRESETS,
        # 'transparente') — verificado empíricamente (diff de píxeles +
        # inspección visual) que SÍ se nota, no es un parámetro sin efecto.
        salida.append('e_shadow:60,co_black')
    salida.append(f'fl_layer_apply,{gravedad},y_{y}')
    return salida


def _capas_multilinea(lineas, posicion, preset):
    alturas = [_alto(l['tamano']) for l in lineas]
    gravedad = _GRAVEDAD[posicion]
    if posicion == 'abajo':
        ys = _offsets_abajo(alturas)
    elif posicion == 'arriba':
        ys = _offsets_arriba(alturas)
    else:
        ys = _offsets_centro(alturas)
    capas = []
    for linea, y in zip(lineas, ys):
        capas.extend(_capas_linea(linea['texto'], TAMANOS[linea['tamano']], y, gravedad, preset))
    return capas


def url_historia(cloud_url, receta, attachment=False):
    """cloud_url del clip + receta → URL del JPG 1080×1920 compuesto.

    Inserta la cadena de transformaciones tras /upload/ (si la URL ya trae una
    transformación propia, queda encadenada — válido en Cloudinary)."""
    lineas = receta.get('lineas') or []
    if not cloud_url or '/upload/' not in cloud_url or not (receta.get('texto') or lineas):
        return ''
    p = PRESETS[receta['preset']]

    capas = [BASE]
    if attachment:
        capas.insert(0, 'fl_attachment:aremko_historia')

    if lineas:
        # Modo "3 líneas con tamaño" (Jorge, 2026-07-26) — cada línea es su
        # propia capa, apiladas sin superponerse (ver _offsets_*).
        capas.extend(_capas_multilinea(lineas, receta['posicion'], p))
    else:
        # Modo clásico: un solo bloque a tamaño 58 (puede traer \n internos
        # de `_cap`) — construcción LITERAL idéntica a antes de este cambio,
        # a propósito: una receta ya guardada sin `lineas` debe renderizar
        # byte-a-byte igual que siempre, sin pasar por la nueva ruta.
        partes = [f"l_text:{FUENTE}_58_center:{_txt(receta['texto'])}", f"co_rgb:{p['texto']}"]
        if p.get('caja'):
            partes.append(f"b_rgb:{p['caja']}")
        partes.append('c_fit,w_860')
        capas.append(','.join(partes))
        if p.get('sombra'):
            capas.append('e_shadow:60,co_black')
        capas.append(f"fl_layer_apply,{POSICIONES[receta['posicion']]}")
    # Sello de marca (chico; el letter_spacing va DENTRO del estilo de la fuente).
    # En NEGRITA real (FUENTE_SELLO) + sombra SIEMPRE (a diferencia del texto
    # principal, que va en FUENTE/regular y solo lleva sombra con el preset
    # 'transparente'): Jorge notó poco protagonismo del sello contra fotos de
    # tonos cálidos (madera) en los 3 presets, 2026-07-26.
    capas.append(
        f"l_text:{FUENTE_SELLO}_26_letter_spacing_6_center:{_txt(SELLO_TEXTO)},"
        f"co_rgb:{p['sello']}")
    capas.append('e_shadow:60,co_black')
    capas.append('fl_layer_apply,g_south,y_180')
    cadena = '/'.join(capas)
    return cloud_url.replace('/upload/', f'/upload/{cadena}/', 1)
