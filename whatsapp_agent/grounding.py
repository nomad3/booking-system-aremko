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


def formatear_servicios(servicios):
    """servicios: iterable de dicts con nombre/precio_base/duracion/descripcion_web/tipo_servicio."""
    lineas = []
    for s in servicios:
        nombre = (s.get('nombre') or '').strip()
        if not nombre:
            continue
        partes = [f'• {nombre}']
        dur = s.get('duracion')
        if dur:
            partes.append(f'({dur} min)')
        partes.append('— ' + formatear_precio(s.get('precio_base')))
        linea = ' '.join(partes)
        desc = _recortar(s.get('descripcion_web'), 140)
        if desc:
            linea += f'. {desc}'
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

    servicios = list(
        Servicio.objects
        .filter(publicado_web=True, activo=True)
        .order_by('tipo_servicio', 'nombre')
        .values('nombre', 'precio_base', 'duracion', 'descripcion_web', 'tipo_servicio')
    )
    productos = list(
        Producto.objects
        .filter(publicado_web=True, cantidad_disponible__gt=0)
        .order_by('orden', 'nombre')
        .values('nombre', 'precio_base', 'descripcion_web')
    )
    return construir_catalogo_texto(servicios, productos)
