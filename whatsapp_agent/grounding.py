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
        # Precio: las cabañas se cobran por la cabaña COMPLETA (precio_base × capacidad,
        # que son SIEMPRE 2 personas). Mostrar el TOTAL evita que Luna liste el precio de
        # 1 persona (bug real: mostraba "$55.000" en vez de "$110.000"). Tinas/masajes SÍ
        # son por persona.
        if s.get('tipo_servicio') == 'cabana':
            cap = s.get('capacidad_maxima') or 2
            total_cabana = int((s.get('precio_base') or 0) * cap)
            partes.append('— ' + formatear_precio(total_cabana) +
                          ' por noche (precio TOTAL de la cabaña para ' + str(cap) +
                          ' personas, NO por persona)')
        else:
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


def construir_catalogo_texto(servicios, productos, ambientaciones=None):
    """Arma el bloque de catálogo (texto) a partir de los dicts ya filtrados.

    Función PURA: recibe listas de dicts, devuelve string. Testeable sin DB.
    """
    bloques = []
    serv_lineas = formatear_servicios(servicios)
    if serv_lineas:
        bloques.append('SERVICIOS PUBLICADOS:\n' + '\n'.join(serv_lineas))
    else:
        bloques.append('SERVICIOS PUBLICADOS:\n(sin servicios publicados en este momento)')

    # H-079: ambientaciones como sección INFORMATIVA. Antes de esto, Luna no sabía
    # que existían (catalogo_vivo solo trae TIPOS_PRINCIPALES) y ante "¿qué
    # ambientaciones tienen?" inventaba poesía (caso real 2026-07-29).
    amb_lineas = []
    for a in (ambientaciones or []):
        nombre = (a.get('nombre') or '').strip()
        if nombre:
            amb_lineas.append(f'• {nombre} — ' + formatear_precio(a.get('precio_base')))
    if amb_lineas:
        bloques.append(
            'AMBIENTACIONES (decoración opcional que acompaña una tina o experiencia; se '
            'prepara para la MISMA hora de la tina, no tiene horario propio):\n'
            + '\n'.join(amb_lineas)
            + '\nSi el cliente pregunta por ambientaciones/decoración, menciona SOLO estas '
              'opciones con su precio (información REAL del catálogo — no inventes otras ni '
              'describas qué incluyen si no lo sabes). Si el cliente quiere una, dile que el '
              'equipo la suma a su cotización — NO la agregues tú al carrito.'
        )

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
    # H-079: ambientaciones activas con precio real (>1 excluye cortesías $0 y
    # centinelas $1) — mismo criterio que el picker del cajón (H-077). Van aparte
    # de `servicios` (son tipo 'otro', nunca chocan con TIPOS_PRINCIPALES) y a
    # propósito NO se filtra publicado_web: son complementos internos, no oferta web.
    ambientaciones = list(
        Servicio.objects
        .filter(activo=True, categoria__nombre__iexact='Ambientaciones', precio_base__gt=1)
        .order_by('nombre')
        .values('nombre', 'precio_base')
    )
    return construir_catalogo_texto(servicios, productos, ambientaciones)
