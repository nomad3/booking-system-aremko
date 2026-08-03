from django import template

register = template.Library()

@register.filter
def formato_clp(value):
    try:
        value = float(value)
        formatted = "{:,.0f}".format(value).replace(",", ".")
        return f"${formatted}"
    except (ValueError, TypeError):
        return value

@register.filter
def duration_in_hours(minutes):
    """Converts duration from minutes to a readable hour/minute format."""
    try:
        minutes = int(minutes)
        if minutes < 60:
            return f"{minutes} minutos"
        else:
            hours = minutes / 60
            # Use .1f for one decimal place, then replace .0 if it's a whole number
            hours_str = "{:.1f}".format(hours).replace('.0', '')
            return f"{hours_str} hora{'s' if hours > 1 else ''}"
    except (ValueError, TypeError, AttributeError):
        return "" # Return empty string if input is invalid


@register.filter
def filter_reserva_web(servicios, value):
    """Filtra una lista de servicios por el campo permite_reserva_web."""
    try:
        target = bool(value)
        return [s for s in servicios if bool(getattr(s, 'permite_reserva_web', False)) == target]
    except (TypeError, AttributeError):
        return []


# Nombres de tinas que tienen hidromasaje (derivado por nombre, sin tocar BD)
TINAS_HIDROMASAJE = {'llaima', 'villarrica', 'puntiagudo', 'puyehue'}


@register.filter
def filter_tinas(servicios):
    """Filtra servicios a solo los de la categoría Tinas (por nombre de categoría)."""
    try:
        result = []
        for s in servicios:
            cat_name = ''
            cat = getattr(s, 'categoria', None)
            if cat is not None:
                cat_name = (getattr(cat, 'nombre', '') or '').lower()
            if 'tina' in cat_name:
                result.append(s)
        return result
    except (TypeError, AttributeError):
        return []


@register.filter
def filter_hidromasaje(servicios, value):
    """Separa tinas por hidromasaje basándose en el nombre. value=1 (con) / 0 (sin)."""
    try:
        target = bool(value)
        result = []
        for s in servicios:
            nombre = (getattr(s, 'nombre', '') or '').lower()
            has_jets = any(n in nombre for n in TINAS_HIDROMASAJE)
            if has_jets == target:
                result.append(s)
        return result
    except (TypeError, AttributeError):
        return []


@register.filter
def multiply(value, arg):
    """Multiplica value × arg. Devuelve 0 si falla."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def order_by_capacity(servicios):
    """Ordena servicios de menor a mayor capacidad_maxima."""
    try:
        return sorted(servicios, key=lambda s: getattr(s, 'capacidad_maxima', 0) or 0)
    except (TypeError, AttributeError):
        return list(servicios) if servicios else []


# Datos confirmados por Jorge 2026-07-12 para las tinas grupales (Calbuco,
# Osorno) — antes solo vivían en un post de blog, ahora también en la ficha
# pública para que quien llega directo a /tinas/ los vea sin tener que
# pasar por el blog.
TINA_GRUPAL_DETALLES_EXTRA = [
    ('fa-clock', 'Horarios: 14:30 o 19:30'),
    ('fa-utensils', 'Trae tu comida y bebida'),
    ('fa-wine-glass', 'Copas y hielo sin costo'),
    ('fa-ban', 'Sin cobro de descorche'),
]


@register.filter
def tina_display(servicio):
    """
    Devuelve overrides de display para tinas según nombre, sin tocar BD.

    Llaves del dict:
      - capacidad_texto: reemplaza el texto de capacidad (ej. "5–6 personas", "1 niño adicional")
      - hide_capacidad: oculta la línea de capacidad
      - duracion_texto: reemplaza el texto de duración (ej. "Uso ilimitado", "4 horas de uso exclusivo")
      - hide_duracion: oculta la línea de duración
      - precio_total: fuerza el precio total mostrado (None = calcular precio_base × capacidad_maxima)
      - unit_note: texto bajo el precio (ej. "por niño adicional", "por tina · 5–6 personas")
      - hook: frase evocadora única por tina (AR-015, hilo narrativo volcánico)
      - detalles_extra: lista de (icono_fontawesome, texto) para chips informativos
        adicionales bajo el hook (ej. horarios, condiciones de uso) — reutiliza el
        patrón visual .cabana-chips ya usado en cabañas
    """
    nombre = (getattr(servicio, 'nombre', '') or '').lower()
    overrides = {
        'capacidad_texto': None,
        'hide_capacidad': False,
        'duracion_texto': None,
        'hide_duracion': False,
        'precio_total': None,
        'unit_note': None,
        'hook': None,
        'es_cortesia': False,
        'detalles_extra': None,
    }
    if 'niño' in nombre or 'nino' in nombre:
        overrides['capacidad_texto'] = '1 niño adicional'
        overrides['hide_duracion'] = True
        try:
            overrides['precio_total'] = float(servicio.precio_base or 0)
        except (TypeError, ValueError):
            overrides['precio_total'] = 0
        overrides['unit_note'] = 'por niño adicional'
        return overrides

    # AR-015: hilo narrativo volcánico único por tina (SEO local + diferenciación)
    # --- Hidromasaje ---
    if 'llaima' in nombre:
        overrides['hook'] = (
            'El volcán más activo de Chile, con más de 50 erupciones '
            'registradas. Hidromasaje con potencia volcánica.'
        )
    elif 'puntiagudo' in nombre:
        overrides['hook'] = (
            'Cono afilado como aguja de basalto, el perfil más '
            'distintivo de la cordillera del sur.'
        )
    elif 'puyehue' in nombre:
        overrides['hook'] = (
            'Parque nacional y aguas termales milenarias. Jets '
            'en el pulso del bosque valdiviano.'
        )
    elif 'villarrica' in nombre:
        overrides['hook'] = (
            'Cráter activo visible desde el sur: cumbre nevada '
            'con fuego eterno en su interior.'
        )
    # --- Tradicionales ---
    elif 'osorno' in nombre:
        overrides['capacidad_texto'] = '5–6 personas'
        overrides['duracion_texto'] = '4 horas de uso exclusivo · grupo 4+'
        overrides['unit_note'] = 'por tina · 5–6 personas'
        overrides['hook'] = (
            'El Fuji chileno: cono perfecto coronado de nieve. '
            'La foto postal del sur, en tu tina privada.'
        )
        overrides['detalles_extra'] = TINA_GRUPAL_DETALLES_EXTRA
    elif 'calbuco' in nombre:
        overrides['capacidad_texto'] = '4 personas'
        overrides['duracion_texto'] = '4 horas de uso exclusivo · grupo 4+'
        overrides['unit_note'] = 'por tina · 4 personas'
        overrides['hook'] = (
            'El gigante que rugió en 2015 con pluma visible a 400km. '
            'Tina grupal para celebrar en grande.'
        )
        overrides['detalles_extra'] = TINA_GRUPAL_DETALLES_EXTRA
    elif 'tronador' in nombre:
        overrides['hook'] = (
            'Tres cumbres entre Chile y Argentina coronadas de '
            'glaciares eternos. El paisaje más imponente del sur.'
        )
    elif 'hornopiren' in nombre or 'hornopirén' in nombre:
        overrides['hook'] = (
            'Fiordo y volcán del sur profundo, puerta de entrada '
            'a la Patagonia. Aguas calientes de la ruta original.'
        )
    elif 'yates' in nombre:
        overrides['duracion_texto'] = 'Uso ilimitado'
        overrides['es_cortesia'] = True
        overrides['unit_note'] = 'Uso libre para todos los huéspedes de Aremko'
        overrides['hook'] = (
            'Volcán remoto en la Patagonia profunda. La tina de '
            'uso ilimitado para quienes buscan desconexión total.'
        )
    return overrides


@register.filter
def imagenes_disponibles(obj):
    """
    Devuelve lista de URLs de imágenes disponibles (imagen, imagen_2, imagen_3)
    para un Servicio o Producto. Omite las vacías.
    """
    urls = []
    for attr in ('imagen', 'imagen_2', 'imagen_3'):
        img = getattr(obj, attr, None)
        if img:
            try:
                urls.append(img.url)
            except (ValueError, AttributeError):
                continue
    return urls


@register.filter
def cabana_display(servicio):
    """
    Overrides de display para la categoría Alojamientos (cabañas + extras).

    Llaves:
      - is_desayuno: bool, cambia el set de specs a ítems de desayuno
      - badge_text / badge_icon: override de la etiqueta superior
      - unit_note: texto bajo el precio
      - hook: frase evocadora única por cabaña (AR-015)
      - quote / quote_source: testimonial real diferenciador (AR-015)
    """
    nombre = (getattr(servicio, 'nombre', '') or '').lower()
    overrides = {
        'is_desayuno': False,
        'badge_text': 'Boutique',
        'badge_icon': 'fa-gem',
        'unit_note': None,
        'hook': None,
        'quote': None,
        'quote_source': None,
    }
    if 'desayuno' in nombre:
        overrides['is_desayuno'] = True
        overrides['badge_text'] = 'Desayuno Boutique'
        overrides['badge_icon'] = 'fa-mug-hot'
        cap = getattr(servicio, 'capacidad_maxima', 1) or 1
        overrides['unit_note'] = f'por desayuno · {cap} persona{"s" if cap > 1 else ""}'
        return overrides

    # Copy único por cabaña (AR-015): hook narrativo + testimonial real
    if 'torre' in nombre:
        overrides['badge_text'] = 'La más demandada'
        overrides['badge_icon'] = 'fa-crown'
        overrides['hook'] = (
            'La única de dos niveles. Torre redonda con dormitorio en la copa, '
            'rodeado por 16 ventanales bajo una cúpula de domo.'
        )
        overrides['quote'] = '2 días aquí equivalen a una semana de vacaciones.'
        overrides['quote_source'] = 'Trip.com'
    elif 'arrayan' in nombre or 'arrayán' in nombre:
        overrides['hook'] = (
            'Por el árbol sagrado de corteza roja sedosa. Refugio íntimo en '
            'maderas recicladas con luz filtrada entre helechos.'
        )
        overrides['quote'] = 'Privacidad en la naturaleza.'
        overrides['quote_source'] = 'Trip.com'
    elif 'coihue' in nombre:
        overrides['hook'] = (
            'Bajo el dosel denso del coihue patagónico. La más tranquila, '
            'orientada al bosque más antiguo del terreno.'
        )
        overrides['quote'] = 'Hace meses no dormía tan bien y tanto.'
        overrides['quote_source'] = 'pilarisl · Trip.com'
    elif 'manio' in nombre or 'mañío' in nombre or 'mañio' in nombre:
        overrides['hook'] = (
            'Homenaje a la conífera de crecimiento lento. Interior cálido '
            'en madera rosada con detalles contemporáneos.'
        )
        overrides['quote'] = 'El lugar es precioso, un lujo en Puerto Varas.'
        overrides['quote_source'] = 'Trip.com'
    elif 'canelo' in nombre:
        overrides['hook'] = (
            'Por el árbol sagrado mapuche de flores blancas aromáticas. '
            'Diseño sobrio que mezcla lo nativo con lo moderno.'
        )
        overrides['quote'] = 'Un refugio para el alma.'
        overrides['quote_source'] = 'Trip.com'
    elif 'ulmo' in nombre:
        overrides['hook'] = (
            'Por la flor blanca que da la miel patagónica. Maderas '
            'recicladas y ventanales orientados al bosque.'
        )
        overrides['quote'] = 'Sounds of nature — I would return a thousand times.'
        overrides['quote_source'] = 'Trip.com'
    elif 'acantilado' in nombre:
        overrides['badge_text'] = 'Vista al río'
        overrides['badge_icon'] = 'fa-water'
        overrides['hook'] = (
            'Al borde del acantilado, con vista al Río Pescado y '
            'la isla que lo divide en dos brazos.'
        )
    elif 'laurel' in nombre:
        overrides['hook'] = (
            'Construida íntegramente en laurel nativo reciclado. '
            'Cada mueble y viga cuenta la historia del bosque.'
        )
    elif 'tepa' in nombre:
        overrides['hook'] = (
            'Junto a un tepa centenario, el árbol más aromático del '
            'bosque valdiviano. Su perfume acompaña el despertar.'
        )
    return overrides


@register.filter
def has_group(user, group_name):
    """True si el usuario pertenece al grupo indicado (por nombre). Uso en templates:
    {% if user|has_group:"Masajistas" %}"""
    try:
        return bool(user) and user.is_authenticated and user.groups.filter(name=group_name).exists()
    except Exception:
        return False


@register.filter
def cuadrada(image_field, size=600):
    """Devuelve la URL de una imagen de Cloudinary recortada a cuadrado inteligente.

    Inserta una transformación Cloudinary (c_fill, ar_1:1, g_auto) que recorta a
    cuadrado enfocando el sujeto, más q_auto/f_auto para optimizar peso y formato.
    Así cualquier foto subida desde el admin luce cuadrada sin recortarla a mano.
    Si la imagen no es de Cloudinary, devuelve la URL original sin tocar.

    Uso: {{ config.foto_hero|cuadrada }}  o  {{ config.foto_acto1|cuadrada:800 }}
    """
    try:
        url = image_field.url if hasattr(image_field, 'url') else str(image_field)
    except Exception:
        return ''
    if not url or '/upload/' not in url:
        return url
    try:
        size = int(size)
    except (ValueError, TypeError):
        size = 600
    transf = f'c_fill,ar_1:1,g_auto,q_auto,f_auto,w_{size}'
    return url.replace('/upload/', f'/upload/{transf}/', 1)


@register.filter
def optimizada(image_field, width=900):
    """URL de una imagen de Cloudinary OPTIMIZADA para entrega web, SIN recortar.

    Inserta `f_auto,q_auto,c_limit,w_<width>`: formato moderno (webp/avif),
    calidad automática y límite de ancho (c_limit = solo achica si es más grande,
    conserva proporción, no agranda ni recorta). Baja muchísimo el peso/ancho de
    banda servido (las fotos full-res de ~1MB pasan a ~100-200KB) y acelera el sitio.
    Si la imagen no es de Cloudinary, devuelve la URL original sin tocar.

    Uso: {{ servicio.imagen|optimizada }}  o  {{ config.hero|optimizada:1600 }}
    """
    try:
        url = image_field.url if hasattr(image_field, 'url') else str(image_field)
    except Exception:
        return ''
    if not url or '/upload/' not in url:
        return url
    try:
        width = int(width)
    except (ValueError, TypeError):
        width = 900
    return url.replace('/upload/', f'/upload/f_auto,q_auto,c_limit,w_{width}/', 1)


# Días de la semana SIN slots configurados, en el índice que usa JavaScript
# (Date.getDay(): 0=domingo … 6=sábado). Se calcula en el servidor para poder
# DESACTIVARLOS en el calendario del modal: bloquear el botón después de elegir
# el día no alcanza — el cliente elige un martes, presiona "Agregar" y no pasa
# nada (caso real reportado por Jorge el 2026-08-02). Mejor que no sea elegible.
_DIA_A_JS = {
    'sunday': 0, 'monday': 1, 'tuesday': 2, 'wednesday': 3,
    'thursday': 4, 'friday': 5, 'saturday': 6,
}


@register.filter
def dias_cerrados_js(slots_disponibles):
    """"2" para un servicio sin martes; "" si no hay nada que desactivar.

    Devuelve vacío cuando el servicio NO declara grilla (mismo criterio permisivo
    que `hora_es_slot_del_dia`: hay servicios que se venden sin horarios) o cuando
    la grilla es una lista simple (mismos horarios todos los días).
    """
    if not slots_disponibles or not isinstance(slots_disponibles, dict):
        return ''
    cerrados = [
        str(js) for nombre, js in sorted(_DIA_A_JS.items(), key=lambda x: x[1])
        if not (slots_disponibles.get(nombre) or [])
    ]
    return ','.join(cerrados)


@register.filter
def hora_llegada(llegadas, reserva_id):
    """'15:04' si esa reserva ya registró llegada, '' si no.

    Existe porque las plantillas de Django no saben buscar en un diccionario con
    una clave variable, y la agenda arma sus tarjetas en cinco lugares distintos:
    meter el dato en cada uno sería garantizar que alguno quede sin él.
    """
    try:
        return (llegadas or {}).get(int(reserva_id)) or ''
    except (TypeError, ValueError):
        return ''
