"""Auto-pick determinista de foto (H-073, Fase 2 de "Creación de Historias").

Regla de oro del M17: el LLM elige UNA sola vez, al escribir el brief semanal
— ahí deja anotado `criterio_foto` (ver `ventas.services.marketing_brief_
generator`). La selección FINAL de la foto acá es 100% código: sin LLM,
determinista y auditable (devuelve el `nivel` de degradación usado). Es lo
correcto porque el modo automático puede publicar sin revisión humana.

Cascada (nivel devuelto, de mejor a peor):
  1. criterio completo + keeper + sin personas + fresca (no usada en `dias`)
  2. igual, sin exigir keeper
  3. igual, relajando momento/decoración (área, nombre y vapor NO se relajan)
  4. igual, permitiendo repetir (la usada hace más tiempo) -> aviso
  5. igual, permitiendo personas (solo si `permitir_personas=True`) -> aviso
  6. nada encontrado -> aviso

`estado='ok'` es un filtro duro en TODOS los niveles: una foto a revisar o
descartada nunca sale por auto-pick, sin importar cuánto se degrade el resto.
"""
from datetime import timedelta

from django.db.models import F, Q
from django.utils import timezone

from .models import Clip

DIAS_FRESCURA_DEFAULT = 60

AVISO_REPETIDA = 'Foto repetida: no había ninguna fresca para este criterio (ya se usó hace poco).'
AVISO_PERSONAS = 'Esta foto tiene personas: revísala antes de publicar.'
AVISO_SIN_FOTO = 'No hay foto para este criterio — elige manual o sube fotos de esta área.'


def _filtro_base(criterio, relajar_momento_decoracion=False, permitir_personas=False):
    """Arma el Q de una pasada de la cascada. `area`, `nombre_comercial` y
    `vapor_preferido` son duros en toda la cascada (nunca se relajan) — solo
    momento/decoración (nivel 3), no-repetir (nivel 4) y personas (nivel 5)
    ceden, y siempre con aviso."""
    q = Q(area=criterio['area'], estado='ok')
    if not permitir_personas:
        q &= Q(personas=False)
    nombre = (criterio.get('nombre_comercial') or '').strip()
    if nombre:
        q &= Q(nombre_comercial__icontains=nombre)
    if criterio.get('vapor_preferido'):
        q &= Q(vapor__in=['sí', 'sí (IA)'])
    if not relajar_momento_decoracion:
        decoracion = (criterio.get('decoracion') or '').strip()
        if decoracion:
            q &= Q(decoracion=decoracion)
        momento = (criterio.get('momento') or 'indistinto').strip()
        if momento != 'indistinto':
            q &= Q(momento=momento)
    return q


def _orden_fresca():
    """Nunca-usada primero (NULLS FIRST explícito: el default de Postgres en
    ASC es NULLS LAST, que dejaría lo nunca-usado al final — justo lo
    contrario de lo que queremos), luego lo usado hace más tiempo. Keeper
    como desempate cuando no se exige (nivel 2+)."""
    return ['-keeper', F('ultimo_uso').asc(nulls_first=True)]


def seleccionar_clip(criterio, dias=DIAS_FRESCURA_DEFAULT, permitir_personas=False, excluir_ids=None):
    """Devuelve (clip, nivel, aviso). `clip` es None si no hay nada (nivel 6).
    `excluir_ids`: ids a saltarse (para "🔄 Otra foto" — misma cascada sin las
    ya mostradas). No lanza: un criterio vacío/corrupto devuelve (None, 6, ...)
    en vez de reventar — el llamador decide si ofrece manual."""
    if not isinstance(criterio, dict) or not (criterio.get('area') or '').strip():
        return None, 6, AVISO_SIN_FOTO

    base_qs = Clip.objects.all()
    if excluir_ids:
        base_qs = base_qs.exclude(id__in=excluir_ids)

    # timezone.localtime(...).date() (NO timezone.now().date()): Django settea
    # TIME_ZONE=America/Santiago pero timezone.now() es UTC — tomar .date() sin
    # localizar da la fecha de MAÑANA entre ~20:00 y medianoche hora Chile.
    corte = timezone.localtime(timezone.now()).date() - timedelta(days=dias)
    fresca = Q(ultimo_uso__isnull=True) | Q(ultimo_uso__lt=corte)

    # Nivel 1: criterio completo + keeper + sin personas + fresca.
    clip = (base_qs.filter(_filtro_base(criterio), keeper=True).filter(fresca)
            .order_by(*_orden_fresca()).first())
    if clip:
        return clip, 1, ''

    # Nivel 2: sin exigir keeper (sigue prefiriéndolo si lo hay, por el order_by).
    clip = (base_qs.filter(_filtro_base(criterio)).filter(fresca)
            .order_by(*_orden_fresca()).first())
    if clip:
        return clip, 2, ''

    # Nivel 3: relaja momento/decoración.
    clip = (base_qs.filter(_filtro_base(criterio, relajar_momento_decoracion=True)).filter(fresca)
            .order_by(*_orden_fresca()).first())
    if clip:
        return clip, 3, ''

    # Nivel 4: permite repetir — la usada hace más tiempo entre las que calzan.
    clip = (base_qs.filter(_filtro_base(criterio, relajar_momento_decoracion=True))
            .order_by(*_orden_fresca()).first())
    if clip:
        return clip, 4, AVISO_REPETIDA

    # Nivel 5: además permite personas — solo si el llamador lo autoriza explícitamente.
    if permitir_personas:
        clip = (base_qs.filter(_filtro_base(criterio, relajar_momento_decoracion=True, permitir_personas=True))
                .order_by(*_orden_fresca()).first())
        if clip:
            return clip, 5, AVISO_PERSONAS

    return None, 6, AVISO_SIN_FOTO
