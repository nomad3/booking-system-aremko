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
    """
    nombre = (getattr(servicio, 'nombre', '') or '').lower()
    overrides = {
        'capacidad_texto': None,
        'hide_capacidad': False,
        'duracion_texto': None,
        'hide_duracion': False,
        'precio_total': None,
        'unit_note': None,
    }
    if 'niño' in nombre or 'nino' in nombre:
        overrides['capacidad_texto'] = '1 niño adicional'
        overrides['hide_duracion'] = True
        try:
            overrides['precio_total'] = float(servicio.precio_base or 0)
        except (TypeError, ValueError):
            overrides['precio_total'] = 0
        overrides['unit_note'] = 'por niño adicional'
    elif 'osorno' in nombre:
        overrides['capacidad_texto'] = '5–6 personas'
        overrides['duracion_texto'] = '4 horas de uso exclusivo · grupo 4+'
        overrides['unit_note'] = 'por tina · 5–6 personas'
    elif 'calbuco' in nombre:
        overrides['capacidad_texto'] = '4 personas'
        overrides['duracion_texto'] = '4 horas de uso exclusivo · grupo 4+'
        overrides['unit_note'] = 'por tina · 4 personas'
    elif 'yates' in nombre:
        overrides['duracion_texto'] = 'Uso ilimitado'
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
