"""
FASE 2: Diccionario de normalización de ciudades

Este archivo contiene el mapeo de todas las variantes de ciudades
encontradas en la base de datos a sus nombres oficiales.

Basado en análisis de datos reales (FASE 1).
"""

# Diccionario de normalización: variante → nombre oficial
NORMALIZACION_CIUDADES = {
    # ============================================
    # PUERTO MONTT (~761 clientes total)
    # ============================================
    'pto montt': 'Puerto Montt',
    'pto. montt': 'Puerto Montt',
    'puerto montt': 'Puerto Montt',
    'puerto Montt': 'Puerto Montt',
    'PUERTO MONTT': 'Puerto Montt',
    'p. montt': 'Puerto Montt',
    'p montt': 'Puerto Montt',
    'Pmontt': 'Puerto Montt',

    # ============================================
    # PUERTO VARAS (~561 clientes total)
    # ============================================
    'pto varas': 'Puerto Varas',
    'pto. varas': 'Puerto Varas',
    'puerto varas': 'Puerto Varas',
    'puerto Varas': 'Puerto Varas',
    'PUERTO VARAS': 'Puerto Varas',
    'p. varas': 'Puerto Varas',
    'p varas': 'Puerto Varas',
    'Pvaras': 'Puerto Varas',

    # ============================================
    # SANTIAGO (~378 clientes)
    # ============================================
    'santiago': 'Santiago',
    'SANTIAGO': 'Santiago',
    'santigo': 'Santiago',  # typo detectado
    'sANTIGO': 'Santiago',  # typo detectado
    'stgo': 'Santiago',
    'stgo.': 'Santiago',

    # ============================================
    # OSORNO (95 clientes)
    # ============================================
    'osorno': 'Osorno',
    'OSORNO': 'Osorno',

    # ============================================
    # VALDIVIA
    # ============================================
    'valdivia': 'Valdivia',
    'VALDIVIA': 'Valdivia',

    # ============================================
    # CONCEPCIÓN
    # ============================================
    'concepcion': 'Concepción',
    'concepción': 'Concepción',
    'CONCEPCION': 'Concepción',
    'conce': 'Concepción',
    'ccp': 'Concepción',

    # ============================================
    # VALPARAÍSO
    # ============================================
    'valparaiso': 'Valparaíso',
    'valparaíso': 'Valparaíso',
    'VALPARAISO': 'Valparaíso',
    'valpo': 'Valparaíso',
    'valpso': 'Valparaíso',

    # ============================================
    # VIÑA DEL MAR
    # ============================================
    'viña del mar': 'Viña del Mar',
    'vina del mar': 'Viña del Mar',
    'VIÑA DEL MAR': 'Viña del Mar',
    'viña': 'Viña del Mar',
    'vina': 'Viña del Mar',

    # ============================================
    # LA SERENA
    # ============================================
    'la serena': 'La Serena',
    'LA SERENA': 'La Serena',
    'laserena': 'La Serena',

    # ============================================
    # TEMUCO
    # ============================================
    'temuco': 'Temuco',
    'TEMUCO': 'Temuco',

    # ============================================
    # ANTOFAGASTA
    # ============================================
    'antofagasta': 'Antofagasta',
    'ANTOFAGASTA': 'Antofagasta',
    'antofa': 'Antofagasta',

    # ============================================
    # ANCUD
    # ============================================
    'ancud': 'Ancud',
    'ANCUD': 'Ancud',

    # ============================================
    # PUNTA ARENAS
    # ============================================
    'punta arenas': 'Punta Arenas',
    'PUNTA ARENAS': 'Punta Arenas',
    'pta. arenas': 'Punta Arenas',
    'pta arenas': 'Punta Arenas',

    # ============================================
    # QUILPUÉ
    # ============================================
    'quilpue': 'Quilpué',
    'QUILPUE': 'Quilpué',
    'quilpúe': 'Quilpué',

    # ============================================
    # RANCAGUA
    # ============================================
    'rancagua': 'Rancagua',
    'RANCAGUA': 'Rancagua',

    # ============================================
    # FRUTILLAR
    # ============================================
    'frutillar': 'Frutillar',
    'FRUTILLAR': 'Frutillar',

    # ============================================
    # LLANQUIHUE
    # ============================================
    'llanquihue': 'Llanquihue',
    'LLANQUIHUE': 'Llanquihue',
    'llaquihue': 'Llanquihue',  # typo común

    # ============================================
    # CALBUCO
    # ============================================
    'calbuco': 'Calbuco',
    'CALBUCO': 'Calbuco',

    # ============================================
    # SAN ANTONIO
    # ============================================
    'san antonio': 'San Antonio',
    'SAN ANTONIO': 'San Antonio',
    'sanantonio': 'San Antonio',

    # ============================================
    # CHILOÉ (ISLA - MÚLTIPLES COMUNAS)
    # ============================================
    'chiloe': 'Chiloé',
    'chiloé': 'Chiloé',
    'CHILOE': 'Chiloé',

    # ============================================
    # CASTRO
    # ============================================
    'castro': 'Castro',
    'CASTRO': 'Castro',

    # ============================================
    # LA UNIÓN
    # ============================================
    'la union': 'La Unión',
    'la unión': 'La Unión',
    'LA UNION': 'La Unión',
    'launion': 'La Unión',

    # ============================================
    # CHILLÁN
    # ============================================
    'chillan': 'Chillán',
    'chillán': 'Chillán',
    'CHILLAN': 'Chillán',

    # ============================================
    # ARICA
    # ============================================
    'arica': 'Arica',
    'ARICA': 'Arica',

    # ============================================
    # IQUIQUE
    # ============================================
    'iquique': 'Iquique',
    'IQUIQUE': 'Iquique',

    # ============================================
    # COYHAIQUE
    # ============================================
    'coyhaique': 'Coyhaique',
    'COYHAIQUE': 'Coyhaique',
    'coihaique': 'Coyhaique',  # typo común

    # ============================================
    # CALAMA
    # ============================================
    'calama': 'Calama',
    'CALAMA': 'Calama',

    # ============================================
    # PUERTO OCTAY
    # ============================================
    'puerto octay': 'Puerto Octay',
    'PUERTO OCTAY': 'Puerto Octay',
    'pto octay': 'Puerto Octay',
    'pto. octay': 'Puerto Octay',

    # ============================================
    # ANGOL
    # ============================================
    'angol': 'Angol',
    'ANGOL': 'Angol',

    # ============================================
    # COCHAMÓ
    # ============================================
    'cochamo': 'Cochamó',
    'cochamó': 'Cochamó',
    'COCHAMO': 'Cochamó',

    # ============================================
    # HORNOPIRÉN
    # ============================================
    'hornopiren': 'Hornopirén',
    'hornopirén': 'Hornopirén',
    'HORNOPIREN': 'Hornopirén',
    'hornopirèn': 'Hornopirén',

    # ============================================
    # PURRANQUE
    # ============================================
    'purranque': 'Purranque',
    'PURRANQUE': 'Purranque',

    # ============================================
    # FRESIA
    # ============================================
    'fresia': 'Fresia',
    'FRESIA': 'Fresia',

    # ============================================
    # CONCÓN
    # ============================================
    'concon': 'Concón',
    'concón': 'Concón',
    'CONCON': 'Concón',

    # ============================================
    # RÍO NEGRO
    # ============================================
    'rio negro': 'Río Negro',
    'río negro': 'Río Negro',
    'RIO NEGRO': 'Río Negro',

    # ============================================
    # PUYEHUE
    # ============================================
    'puyehue': 'Puyehue',
    'PUYEHUE': 'Puyehue',

    # ============================================
    # MAULLÍN
    # ============================================
    'maullin': 'Maullín',
    'maullín': 'Maullín',
    'MAULLIN': 'Maullín',

    # ============================================
    # PUERTO AYSÉN
    # ============================================
    'puerto aysen': 'Puerto Aysén',
    'puerto aysén': 'Puerto Aysén',
    'PUERTO AYSEN': 'Puerto Aysén',
    'pto aysen': 'Puerto Aysén',
    'pto. aysén': 'Puerto Aysén',

    # ============================================
    # LOS ÁNGELES
    # ============================================
    'los angeles': 'Los Ángeles',
    'los ángeles': 'Los Ángeles',
    'LOS ANGELES': 'Los Ángeles',

    # ============================================
    # SANTO DOMINGO
    # ============================================
    'santo domingo': 'Santo Domingo',
    'SANTO DOMINGO': 'Santo Domingo',

    # ============================================
    # RÍO BUENO
    # ============================================
    'rio bueno': 'Río Bueno',
    'río bueno': 'Río Bueno',
    'RIO BUENO': 'Río Bueno',

    # ============================================
    # FUTRONO
    # ============================================
    'futrono': 'Futrono',
    'FUTRONO': 'Futrono',

    # ============================================
    # SANTA CRUZ
    # ============================================
    'santa cruz': 'Santa Cruz',
    'SANTA CRUZ': 'Santa Cruz',
}


def normalizar_ciudad(ciudad_str):
    """
    Normaliza una ciudad a su nombre oficial.

    Args:
        ciudad_str: String con el nombre de la ciudad (puede tener variantes)

    Returns:
        String con el nombre oficial de la ciudad, o el original si no se encuentra mapeo

    Examples:
        >>> normalizar_ciudad("pto montt")
        'Puerto Montt'
        >>> normalizar_ciudad("SANTIAGO")
        'Santiago'
        >>> normalizar_ciudad("p. varas")
        'Puerto Varas'
    """
    if not ciudad_str or not ciudad_str.strip():
        return None

    # Limpiar string
    ciudad_clean = ciudad_str.strip()

    # Buscar en diccionario (case-insensitive)
    ciudad_lower = ciudad_clean.lower()

    if ciudad_lower in NORMALIZACION_CIUDADES:
        return NORMALIZACION_CIUDADES[ciudad_lower]

    # Si no está en el diccionario, retornar con capitalización estándar
    # (Primera letra mayúscula)
    return ciudad_clean.title()


def obtener_variantes_detectadas():
    """
    Retorna todas las variantes conocidas agrupadas por ciudad oficial.

    Returns:
        Dict con ciudad oficial como key y lista de variantes como value
    """
    variantes_por_ciudad = {}

    for variante, oficial in NORMALIZACION_CIUDADES.items():
        if oficial not in variantes_por_ciudad:
            variantes_por_ciudad[oficial] = []
        variantes_por_ciudad[oficial].append(variante)

    return variantes_por_ciudad


# Metadata
TOTAL_VARIANTES = len(NORMALIZACION_CIUDADES)
TOTAL_CIUDADES_OFICIALES = len(set(NORMALIZACION_CIUDADES.values()))

if __name__ == "__main__":
    print(f"Diccionario de normalización cargado:")
    print(f"  - {TOTAL_VARIANTES} variantes mapeadas")
    print(f"  - {TOTAL_CIUDADES_OFICIALES} ciudades oficiales")
    print()

    # Ejemplos
    print("Ejemplos de normalización:")
    ejemplos = [
        "pto montt",
        "SANTIAGO",
        "puerto varas",
        "concepcion",
        "valparaiso"
    ]

    for ej in ejemplos:
        print(f"  '{ej}' → '{normalizar_ciudad(ej)}'")
