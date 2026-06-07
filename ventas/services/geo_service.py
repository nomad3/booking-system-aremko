"""Servicio ÚNICO de clasificación geográfica de clientes (Plan Geo, Etapa E0).

Deriva (ciudad_normalizada, region_geografica) a partir de país + ciudad (texto
libre) + comuna (FK) + región (FK), usando el catálogo `Ciudad` como fuente de
verdad. Lo usan:
  - `Cliente.save()` → derivación automática al guardar (ver ventas/models.py)
  - el comando `normalizar_ciudades_clientes` → backfill masivo

Regla (primer match gana):
  1. Texto con marcador de país extranjero → `extranjero`.
  2. Ciudad (texto) matchea el catálogo (canónico/alias) → región del catálogo.
  3. País explícito ≠ Chile → `extranjero`.
  4. Comuna (FK) matchea el catálogo → región del catálogo.
  5. Comuna (FK) chilena sin match → `nacional` (no está en el set sur).
  6. Ciudad (texto) sin match, país Chile o vacío → `nacional` (ciudad chilena
     fuera del catálogo, ej. "Olmué").
  7. Nada de lo anterior → `sin_clasificar`.

Respeta ediciones manuales en el caller (Cliente.ciudad_normalizada_manual).
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

# Marcadores textuales de país NO-Chile (match case-insensitive por substring).
MARCADORES_EXTRANJERO = [
    'argentina', 'brasil', 'brazil', 'uruguay', 'peru', 'perú', 'bolivia',
    'colombia', 'ecuador', 'usa', 'eeuu', 'ee.uu', 'estados unidos',
    'mexico', 'méxico', 'españa', 'spain', 'francia', 'france',
    'alemania', 'germany', 'italia', 'italy', 'inglaterra', 'uk',
    'noruega', 'norway', 'bélgica', 'belgium', 'belgica',
    'buenos aires', 'mendoza', 'sao paulo', 'são paulo', 'sao pablo',
    'rio de janeiro', 'lima', 'madrid', 'barcelona', 'paris', 'london',
    'miami', 'new york', 'denver', 'dallas', 'guadalajara',
    'oslo', 'bruselas', 'brussels', 'neuquén', 'neuquen', 'santa fe, nm',
]

# Valores de país que consideramos Chile (o "no informado").
CHILE_VALUES = ('', 'chile', 'cl')


def _normalizar(texto: str) -> str:
    """lower + trim + colapsa espacios + sin puntos/comas (para comparar)."""
    if not texto:
        return ''
    s = texto.strip().lower()
    s = re.sub(r'\s+', ' ', s)
    return s.replace('.', '').replace(',', '')


def _es_extranjero_por_texto(texto: str) -> bool:
    if not texto:
        return False
    s = texto.lower()
    return any(m in s for m in MARCADORES_EXTRANJERO)


class LookupCiudades:
    """Preíndice del catálogo Ciudad para lookup O(1) en memoria."""

    def __init__(self):
        self.por_canonico: Dict[str, object] = {}
        self.por_alias: Dict[str, object] = {}
        self.extranjero_generico = None
        self._cargar()

    def _cargar(self):
        from ventas.models import Ciudad
        for ciudad in Ciudad.objects.filter(activo=True):
            if ciudad.nombre_canonico == '_otros_extranjero_':
                self.extranjero_generico = ciudad
                continue
            self.por_canonico[_normalizar(ciudad.nombre_canonico)] = ciudad
            for alias in ciudad.aliases_list():
                self.por_alias[_normalizar(alias)] = ciudad

    def lookup(self, texto: str):
        clave = _normalizar(texto)
        if not clave:
            return None
        return self.por_canonico.get(clave) or self.por_alias.get(clave)


# --- Cache a nivel de proceso (el catálogo cambia muy rara vez) -------------
_LOOKUP: Optional[LookupCiudades] = None


def get_lookup(refresh: bool = False) -> LookupCiudades:
    """Devuelve el lookup cacheado. `refresh=True` lo reconstruye (úsalo en el
    comando de backfill; el proceso web lo refresca al reiniciar/deploy)."""
    global _LOOKUP
    if _LOOKUP is None or refresh:
        _LOOKUP = LookupCiudades()
    return _LOOKUP


def clasificar(pais, ciudad_texto, comuna, region=None, lookup: Optional[LookupCiudades] = None) -> Tuple[str, Optional[object], str]:
    """Devuelve (metodo, ciudad_normalizada|None, region_geografica)."""
    lk = lookup or get_lookup()
    ciudad_texto = (ciudad_texto or '').strip()
    pais_texto = (pais or '').strip().lower()

    # 1. Extranjero por texto (gana sobre canónico en caso ambiguo).
    if ciudad_texto and _es_extranjero_por_texto(ciudad_texto):
        return ('extranjero_texto', lk.extranjero_generico, 'extranjero')

    # 2. Match por ciudad (texto).
    if ciudad_texto:
        match = lk.lookup(ciudad_texto)
        if match:
            metodo = 'match_canonico' if _normalizar(ciudad_texto) in lk.por_canonico else 'match_alias'
            return (metodo, match, match.region_geografica)

    # 3. País explícito no-Chile.
    if pais_texto and pais_texto not in CHILE_VALUES:
        return ('extranjero_pais', lk.extranjero_generico, 'extranjero')

    # 4/5. Comuna estructurada (chilena por definición del modelo).
    comuna_nombre = getattr(comuna, 'nombre', '') if comuna is not None else ''
    if comuna_nombre:
        match = lk.lookup(comuna_nombre)
        if match:
            return ('inferencia_comuna', match, match.region_geografica)
        return ('comuna_nacional', None, 'nacional')

    # 6. Ciudad (texto) chilena fuera del catálogo (país Chile o no informado).
    if ciudad_texto and pais_texto in CHILE_VALUES:
        return ('nacional_inferido', None, 'nacional')

    # 7. Sin datos suficientes.
    return ('sin_match', None, 'sin_clasificar')


def clasificar_cliente(cliente, lookup: Optional[LookupCiudades] = None) -> Tuple[str, Optional[object], str]:
    """Clasifica usando los campos del Cliente."""
    return clasificar(cliente.pais, cliente.ciudad, cliente.comuna, cliente.region, lookup)
