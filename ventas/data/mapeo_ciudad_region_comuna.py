"""
FASE 4: Diccionario de mapeo ciudad → región + comuna

Este archivo mapea las ciudades normalizadas (FASE 3) a región y comuna.

Formato:
    'Ciudad Normalizada': ('CODIGO_REGION', 'Nombre Comuna')

Basado en:
- Fixtures de regiones y comunas de Chile
- Ciudades reales detectadas en base de datos (FASE 1)
"""

# Diccionario de mapeo: ciudad_normalizada → (codigo_region, nombre_comuna)
MAPEO_CIUDAD_REGION_COMUNA = {
    # ============================================
    # REGIÓN DE LOS LAGOS (X)
    # ============================================
    'Puerto Montt': ('X', 'Puerto Montt'),
    'Puerto Varas': ('X', 'Puerto Varas'),
    'Osorno': ('X', 'Osorno'),
    'Castro': ('X', 'Castro'),
    'Ancud': ('X', 'Ancud'),
    'Frutillar': ('X', 'Frutillar'),
    'Llanquihue': ('X', 'Llanquihue'),
    'Calbuco': ('X', 'Calbuco'),
    'Puerto Octay': ('X', 'Puerto Octay'),
    'Cochamó': ('X', 'Cochamó'),
    'Hornopirén': ('X', 'Hornopirén'),
    'Purranque': ('X', 'Purranque'),
    'Fresia': ('X', 'Fresia'),
    'Río Negro': ('X', 'Río Negro'),
    'Puyehue': ('X', 'Puyehue'),
    'Maullín': ('X', 'Maullín'),
    'Chiloé': ('X', 'Castro'),  # Chiloé es isla, usar Castro como comuna principal

    # ============================================
    # REGIÓN METROPOLITANA (RM)
    # ============================================
    'Santiago': ('RM', 'Santiago'),

    # ============================================
    # REGIÓN DE VALPARAÍSO (V)
    # ============================================
    'Valparaíso': ('V', 'Valparaíso'),
    'Viña del Mar': ('V', 'Viña del Mar'),
    'Concón': ('V', 'Concón'),
    'Quilpué': ('V', 'Quilpué'),
    'San Antonio': ('V', 'San Antonio'),
    'Santo Domingo': ('V', 'Santo Domingo'),

    # ============================================
    # REGIÓN DE LOS RÍOS (XIV)
    # ============================================
    'Valdivia': ('XIV', 'Valdivia'),
    'La Unión': ('XIV', 'La Unión'),
    'Río Bueno': ('XIV', 'Río Bueno'),
    'Futrono': ('XIV', 'Futrono'),

    # ============================================
    # REGIÓN DEL BIOBÍO (VIII)
    # ============================================
    'Concepción': ('VIII', 'Concepción'),
    'Los Ángeles': ('VIII', 'Los Ángeles'),

    # ============================================
    # REGIÓN DE ÑUBLE (XVI)
    # ============================================
    'Chillán': ('XVI', 'Chillán'),

    # ============================================
    # REGIÓN DE LA ARAUCANÍA (IX)
    # ============================================
    'Temuco': ('IX', 'Temuco'),
    'Angol': ('IX', 'Angol'),

    # ============================================
    # REGIÓN DE AYSÉN (XI)
    # ============================================
    'Puerto Aysén': ('XI', 'Puerto Aysén'),
    'Coyhaique': ('XI', 'Coyhaique'),

    # ============================================
    # REGIÓN DE MAGALLANES (XII)
    # ============================================
    'Punta Arenas': ('XII', 'Punta Arenas'),

    # ============================================
    # REGIÓN DE COQUIMBO (IV)
    # ============================================
    'La Serena': ('IV', 'La Serena'),

    # ============================================
    # REGIÓN DE O'HIGGINS (VI)
    # ============================================
    'Rancagua': ('VI', 'Rancagua'),
    'Santa Cruz': ('VI', 'Santa Cruz'),

    # ============================================
    # REGIÓN DE ANTOFAGASTA (II)
    # ============================================
    'Antofagasta': ('II', 'Antofagasta'),
    'Calama': ('II', 'Calama'),

    # ============================================
    # REGIÓN DE TARAPACÁ (I)
    # ============================================
    'Iquique': ('I', 'Iquique'),

    # ============================================
    # REGIÓN DE ARICA Y PARINACOTA (XV)
    # ============================================
    'Arica': ('XV', 'Arica'),

    # ============================================
    # CASOS ESPECIALES / EXTRANJEROS
    # ============================================
    # Isla de Pascua (técnicamente Región de Valparaíso, pero muy especial)
    'Isla de Pascua': ('V', 'Isla de Pascua'),

    # Casos extranjeros - no mapear región/comuna
    # Estos quedarán con region=None, comuna=None
    'Estados Unidos': (None, None),
    'Santa Fe, NM': (None, None),
    'El Cajón, CA': (None, None),
    'Argentina': (None, None),
    'Buenos Aires': (None, None),
    'Extranjero': (None, None),
}


def obtener_region_comuna(ciudad_normalizada):
    """
    Obtiene la región y comuna para una ciudad normalizada.

    Args:
        ciudad_normalizada (str): Ciudad normalizada (ej: 'Puerto Montt')

    Returns:
        tuple: (codigo_region, nombre_comuna) o (None, None) si no se encuentra

    Examples:
        >>> obtener_region_comuna('Puerto Montt')
        ('X', 'Puerto Montt')
        >>> obtener_region_comuna('Santiago')
        ('RM', 'Santiago')
        >>> obtener_region_comuna('Estados Unidos')
        (None, None)
    """
    return MAPEO_CIUDAD_REGION_COMUNA.get(ciudad_normalizada, (None, None))


def ciudades_sin_mapeo(lista_ciudades):
    """
    Identifica ciudades que no tienen mapeo definido.

    Args:
        lista_ciudades (list): Lista de ciudades normalizadas

    Returns:
        set: Conjunto de ciudades sin mapeo
    """
    sin_mapeo = set()
    for ciudad in lista_ciudades:
        if ciudad and ciudad not in MAPEO_CIUDAD_REGION_COMUNA:
            sin_mapeo.add(ciudad)
    return sin_mapeo


# Metadata
TOTAL_CIUDADES_MAPEADAS = len([k for k, v in MAPEO_CIUDAD_REGION_COMUNA.items() if v != (None, None)])
TOTAL_CIUDADES_EXTRANJERAS = len([k for k, v in MAPEO_CIUDAD_REGION_COMUNA.items() if v == (None, None)])

if __name__ == "__main__":
    print(f"Diccionario de mapeo ciudad → región + comuna:")
    print(f"  - {TOTAL_CIUDADES_MAPEADAS} ciudades chilenas mapeadas")
    print(f"  - {TOTAL_CIUDADES_EXTRANJERAS} ciudades extranjeras (sin región/comuna)")
    print(f"  - {len(MAPEO_CIUDAD_REGION_COMUNA)} entradas totales")
    print()

    # Ejemplos
    print("Ejemplos de mapeo:")
    ejemplos = ['Puerto Montt', 'Santiago', 'Valparaíso', 'Estados Unidos']
    for ciudad in ejemplos:
        region, comuna = obtener_region_comuna(ciudad)
        if region:
            print(f"  '{ciudad}' → Región {region}, Comuna {comuna}")
        else:
            print(f"  '{ciudad}' → Extranjero (sin región/comuna)")
