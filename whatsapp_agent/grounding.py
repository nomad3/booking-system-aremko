"""Grounding: inyecta el catálogo VIVO de Aremko en cada llamada al LLM.

El agente solo puede hablar de:
  - Servicios PUBLICADOS en la web (`publicado_web=True`, `activo=True`).
  - Productos con STOCK (`publicado_web=True`, `cantidad_disponible > 0`).

Precios y disponibilidad salen siempre de la BD en vivo, nunca hardcodeados.
Las funciones de formato son puras (sin DB) para poder testearlas aisladas.
"""


def formatear_precio(valor):
    """123456 -> '$123.456' (separador de miles chileno con punto)."""
    try:
        entero = int(valor)
    except (TypeError, ValueError):
        return '$0'
    return '$' + f'{entero:,}'.replace(',', '.')


def _recortar(texto, limite=160):
    texto = (texto or '').strip().replace('\n', ' ')
    if len(texto) <= limite:
        return texto
    return texto[:limite].rstrip() + '…'


def formatear_duracion(minutos):
    """240 -> '4 h' · 90 -> '1 h 30 min' · 45 -> '45 min' · 0/None -> ''."""
    try:
        m = int(minutos)
    except (TypeError, ValueError):
        return ''
    if m <= 0:
        return ''
    h, mm = divmod(m, 60)
    if h and mm:
        return f'{h} h {mm} min'
    if h:
        return f'{h} h'
    return f'{mm} min'


def formatear_capacidad(cap_min, cap_max):
    """'para 1 a 4 personas' / 'para 4 personas' (min==max) / '' (capacidad 1)."""
    try:
        lo = int(cap_min) if cap_min is not None else None
        hi = int(cap_max) if cap_max is not None else None
    except (TypeError, ValueError):
        return ''
    if not hi or hi <= 1:
        return ''  # capacidad 1 (default) no agrega contexto
    if lo and lo > 1 and lo == hi:
        return f'para {hi} personas'          # cupo fijo (ej. tina para 4)
    if lo and lo >= 1 and lo != hi:
        return f'para {lo} a {hi} personas'    # rango
    return f'para hasta {hi} personas'         # min desconocido


def formatear_servicios(servicios):
    """servicios: dicts con nombre/precio_base/duracion/descripcion_web/capacidad_minima/
    capacidad_maxima/informacion_adicional."""
    lineas = []
    for s in servicios:
        nombre = (s.get('nombre') or '').strip()
        if not nombre:
            continue
        partes = [f'• {nombre}']
        # Cabañas se expresan "por noche", no en horas (H-011 refinamiento).
        if s.get('tipo_servicio') == 'cabana':
            partes.append('(por noche)')
        else:
            dur = formatear_duracion(s.get('duracion'))
            if dur:
                partes.append(f'({dur})')
        partes.append('— ' + formatear_precio(s.get('precio_base')) + ' por persona')
        # Capacidad (dato estructurado ya en BD): clave para tinas/cabañas.
        cap = formatear_capacidad(s.get('capacidad_minima'), s.get('capacidad_maxima'))
        if cap:
            partes.append(cap)
        linea = ' '.join(partes)
        desc = _recortar(s.get('descripcion_web'), 140)
        if desc:
            linea += f'. {desc}'
        incluye = _recortar(s.get('informacion_adicional'), 140)
        if incluye:
            linea += f' Incluye/nota: {incluye}'
        lineas.append(linea)
    return lineas


def formatear_productos(productos):
    """productos: iterable de dicts con nombre/precio_base/descripcion_web."""
    lineas = []
    for p in productos:
        nombre = (p.get('nombre') or '').strip()
        if not nombre:
            continue
        linea = f'• {nombre} — ' + formatear_precio(p.get('precio_base'))
        desc = _recortar(p.get('descripcion_web'), 100)
        if desc:
            linea += f'. {desc}'
        lineas.append(linea)
    return lineas


def construir_catalogo_texto(servicios, productos):
    """Arma el bloque de catálogo (texto) a partir de los dicts ya filtrados.

    Función PURA: recibe listas de dicts, devuelve string. Testeable sin DB.
    """
    bloques = []
    serv_lineas = formatear_servicios(servicios)
    if serv_lineas:
        bloques.append('SERVICIOS PUBLICADOS:\n' + '\n'.join(serv_lineas))
    else:
        bloques.append('SERVICIOS PUBLICADOS:\n(sin servicios publicados en este momento)')

    prod_lineas = formatear_productos(productos)
    if prod_lineas:
        bloques.append('PRODUCTOS DISPONIBLES (con stock):\n' + '\n'.join(prod_lineas))
    # Si no hay productos con stock, simplemente no se incluye el bloque.

    return '\n\n'.join(bloques)


def catalogo_vivo():
    """Lee la BD en vivo y devuelve el texto del catálogo para el prompt.

    Import local de los modelos de `ventas` para evitar import circular en carga.
    """
    from ventas.models import Servicio, Producto

    from .models import WhatsAppAgentConfig
    from .availability import TIPOS_PRINCIPALES
    comp_ids = WhatsAppAgentConfig.get_solo().ids_complementarios()

    servicios = list(
        Servicio.objects
        .filter(publicado_web=True, activo=True, tipo_servicio__in=TIPOS_PRINCIPALES)
        .exclude(id__in=comp_ids)  # H-011: no listar complementos como ofrecibles
        .order_by('tipo_servicio', 'nombre')
        .values('nombre', 'precio_base', 'duracion', 'descripcion_web', 'tipo_servicio',
                'capacidad_minima', 'capacidad_maxima', 'informacion_adicional')
    )
    productos = list(
        Producto.objects
        .filter(publicado_web=True, cantidad_disponible__gt=0)
        .order_by('orden', 'nombre')
        .values('nombre', 'precio_base', 'descripcion_web')
    )
    return construir_catalogo_texto(servicios, productos)
