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

# Tipografía (set estándar de Cloudinary para overlays; port-friendly: para otro
# tenant se cambia el kit acá o se sube su fuente).
FUENTE = 'Montserrat'

# Presets boutique (Angélica ELIGE, no diseña): colores de marca Aremko.
# 'velo'  = texto crema sobre velo oscuro cálido (para fotos luminosas/día).
# 'crema' = caja crema con texto verde bosque (para fotos oscuras/noche).
PRESETS = {
    'velo': {'texto': 'F2E8D8', 'caja': '1E191299', 'sello': 'F2E8D8'},
    'crema': {'texto': '1E4438', 'caja': 'F2E8D8E0', 'sello': 'F2E8D8'},
}
PRESET_DEFAULT = 'velo'

# Posición del texto (gravity + offset) respetando la zona segura de IG.
POSICIONES = {
    'arriba': 'g_north,y_300',
    'centro': 'g_center,y_0',
    'abajo': 'g_south,y_380',
}
POSICION_DEFAULT = 'abajo'

# Sello de marca, siempre abajo (dentro de la zona segura).
SELLO_TEXTO = 'AREMKO · AGUAS CALIENTES JUNTO AL RÍO'


def _txt(texto):
    """Texto → doble URL-encoding (lo exige Cloudinary para , / % en l_text)."""
    return quote(quote(texto, safe=''), safe='')


def _cap(texto, maximo=220):
    """El texto de una historia es corto por diseño (y la URL, finita)."""
    t = ' '.join((texto or '').split())
    return t[:maximo]


def receta_normalizada(texto, posicion=None, preset=None):
    """Valida/normaliza la receta (lista blanca — nunca inyectar al URL directo)."""
    return {
        'texto': _cap(texto),
        'posicion': posicion if posicion in POSICIONES else POSICION_DEFAULT,
        'preset': preset if preset in PRESETS else PRESET_DEFAULT,
    }


def url_historia(cloud_url, receta, attachment=False):
    """cloud_url del clip + receta → URL del JPG 1080×1920 compuesto.

    Inserta la cadena de transformaciones tras /upload/ (si la URL ya trae una
    transformación propia, queda encadenada — válido en Cloudinary)."""
    if not cloud_url or '/upload/' not in cloud_url or not receta.get('texto'):
        return ''
    p = PRESETS[receta['preset']]
    pos = POSICIONES[receta['posicion']]

    capas = [BASE]
    if attachment:
        capas.insert(0, 'fl_attachment:aremko_historia')
    # Texto principal: envuelve a 860px (c_fit dentro de la capa) y se POSICIONA
    # con fl_layer_apply (sintaxis Cloudinary: la capa y su colocación van en
    # componentes separados — validado empíricamente contra el cloud real).
    capas.append(
        f"l_text:{FUENTE}_58_bold_center:{_txt(receta['texto'])},"
        f"co_rgb:{p['texto']},b_rgb:{p['caja']},c_fit,w_860")
    capas.append(f'fl_layer_apply,{pos}')
    # Sello de marca (chico; el letter_spacing va DENTRO del estilo de la fuente).
    capas.append(
        f"l_text:{FUENTE}_26_letter_spacing_6_center:{_txt(SELLO_TEXTO)},"
        f"co_rgb:{p['sello']}")
    capas.append('fl_layer_apply,g_south,y_180')
    cadena = '/'.join(capas)
    return cloud_url.replace('/upload/', f'/upload/{cadena}/', 1)
