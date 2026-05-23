"""
taxonomia_movimientos_service
=============================

Lógica de soporte para registrar movimientos de taxonomía (Bitácora Viva)
y disparar celebraciones cuando un cliente da un salto positivo notable.

Operación Vuelta a Casa, Etapa 5 — *sin tocar todavía el cron productivo*.

Etapa 5.1 (este commit): detectar_cambios + utilidades de normalización.
Etapa 5.2 (siguiente commit): generar_movimientos_y_celebraciones +
                              detectar_celebraciones + mensajes.
Etapa 5.3 (después del deploy validado): integración en
                              recalcular_taxonomia_clientes detrás de un
                              flag opt-in --registrar-movimientos.

Funciones puras (sin DB), testeable sin runner pesado.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional


# ============================================================================
# Modelo de datos: un cambio detectado en un eje específico
# ============================================================================

@dataclass(frozen=True)
class Cambio:
    """Un cambio detectado entre dos snapshots de taxonomía.

    Attributes:
        eje: nombre del eje afectado: 'valor', 'estilo' o 'contexto'
        valor_antes: string del valor previo (puede ser '' para cliente nuevo)
        valor_despues: string del valor nuevo

    frozen=True → hashable, permite usar Cambio en sets/dicts si se necesita.
    """
    eje: str
    valor_antes: str
    valor_despues: str

    def __str__(self) -> str:
        antes_repr = self.valor_antes or '(sin clasificar)'
        return f"{self.eje}: {antes_repr} → {self.valor_despues}"


# Los 3 ejes que la taxonomía rastrea. Orden importa solo para
# determinismo de iteración en detectar_cambios y tests.
EJES = ('valor', 'estilo', 'contexto')


# ============================================================================
# Normalización: aceptamos dict, ClienteTaxonomia instance, o None
# ============================================================================

def taxonomia_a_dict(taxo: Any) -> dict:
    """Normaliza distintos formatos de taxonomía a un dict de 3 keys.

    Acepta:
      - None (cliente sin taxonomía previa) → {'eje_valor': '', ...}
      - dict con keys eje_valor/eje_estilo/eje_contexto
      - instancia con esos atributos (ClienteTaxonomia, mock, etc.)

    Devuelve dict con exactamente:
        {'eje_valor': str, 'eje_estilo': str, 'eje_contexto': str}

    Garantiza strings no-None (convierte None a '').
    """
    if taxo is None:
        return {'eje_valor': '', 'eje_estilo': '', 'eje_contexto': ''}

    if isinstance(taxo, dict):
        return {
            'eje_valor': str(taxo.get('eje_valor', '') or ''),
            'eje_estilo': str(taxo.get('eje_estilo', '') or ''),
            'eje_contexto': str(taxo.get('eje_contexto', '') or ''),
        }

    # Asumir objeto con atributos (ClienteTaxonomia instance, mock, etc.)
    return {
        'eje_valor': str(getattr(taxo, 'eje_valor', '') or ''),
        'eje_estilo': str(getattr(taxo, 'eje_estilo', '') or ''),
        'eje_contexto': str(getattr(taxo, 'eje_contexto', '') or ''),
    }


# ============================================================================
# Detección de cambios
# ============================================================================

def detectar_cambios(taxo_anterior: Any, taxo_nuevo: Any) -> List[Cambio]:
    """Compara dos snapshots de taxonomía y devuelve los cambios por eje.

    Args:
        taxo_anterior: estado previo del cliente (None / dict / modelo)
        taxo_nuevo:    estado nuevo del cliente (None / dict / modelo)

    Returns:
        Lista de Cambio (puede ser vacía si no hay diferencias).
        Si taxo_anterior es None y taxo_nuevo tiene valores, devuelve un
        Cambio por cada eje con valor_antes='' (cliente recién clasificado).

    No tiene side effects — pura comparación.

    Edge cases:
      - Ambos None → []
      - Mismos valores en todos los ejes → []
      - Un eje cambia → [1 Cambio]
      - Los 3 ejes cambian → [3 Cambios] (en orden EJES)
      - taxo_nuevo tiene valor None en un eje → trata como ''
    """
    antes = taxonomia_a_dict(taxo_anterior)
    nuevo = taxonomia_a_dict(taxo_nuevo)

    cambios: List[Cambio] = []
    for eje in EJES:
        key = f'eje_{eje}'
        v_antes = antes[key]
        v_despues = nuevo[key]
        if v_antes != v_despues:
            cambios.append(Cambio(
                eje=eje,
                valor_antes=v_antes,
                valor_despues=v_despues,
            ))
    return cambios
