"""Sección «Decisiones de la semana» del brief (H-067).

Lee las métricas reales por publicación (contrato docs/CONTRATO_H-067_METRICAS.md,
cosechadas por aremko-cli desde Instagram Graph) y las convierte en un bloque
compacto para la PASADA 1 del brief: ranking top/bottom por "tasa valiosa" + la
meta-métrica % publicado-sin-editar. Es el modelo de apoyo a decisiones de Jorge:
persistir con lo positivo, no insistir con lo negativo, re-enfocar lo mediocre.

Si aún no hay métricas cosechadas devuelve '' y el brief sale igual que siempre.
"""
import logging
from datetime import timedelta
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Umbral de similitud para considerar que el caption se publicó "sin editar".
# Pedido Datamatic (contrato H-067): comparación TOLERANTE — normalizar y usar
# similitud, NUNCA igualdad exacta (un espacio movido sesgaría la meta-métrica).
UMBRAL_SIN_EDITAR = 0.95


def _normalizar_caption(texto):
    """Colapsa espacios/saltos de línea y bordes — solo para comparar."""
    return ' '.join((texto or '').split())


def caption_sin_editar(generado, publicado):
    """True si el caption publicado ≈ el generado (ratio ≥ 0.95 tras normalizar).

    None si falta alguno de los dos (no evaluable: no cuenta en el %).
    """
    gen = _normalizar_caption(generado)
    pub = _normalizar_caption(publicado)
    if not gen or not pub:
        return None
    return SequenceMatcher(None, gen, pub).ratio() >= UMBRAL_SIN_EDITAR


def _caption_generado(pub):
    """El caption que generó el sistema para esa pieza (insumo del % sin-editar).

    Para filas TikTok (H-063) `caption_completo` ya viene con el caption nativo
    derivado; para GBP el copy vive en `texto`.
    """
    cj = pub.copy_json or {}
    return cj.get('caption_completo') or cj.get('texto') or ''


def _fmt_fila(f):
    return (
        f"- [sem {f['semana']}] {f['pieza']} ({f['canal']}) «{f['titulo']}» — "
        f"valiosa {f['valiosa'] * 100:.1f}% · reach {f['reach']} · "
        f"saves {f['saves']} · shares {f['shares']}"
    )


def recolectar_decisiones(semana_inicio, semanas=4):
    """Bloque de texto para la pasada 1 con las métricas reales, o '' si no hay.

    Rankea por `tasas.valiosa` (desempate: reach) según el contrato H-067 y la
    jerarquía de Jorge. Nunca lanza: cualquier error devuelve '' (el brief del
    lunes no puede caerse por métricas).
    """
    try:
        from .models import PublicacionPlanificada

        desde = semana_inicio - timedelta(weeks=semanas)
        pubs = (
            PublicacionPlanificada.objects
            .filter(semana_inicio__gte=desde, semana_inicio__lt=semana_inicio)
            .exclude(metricas={})
        )

        filas, sin_editar_flags = [], []
        for p in pubs:
            m = p.metricas or {}
            if not m.get('v'):
                continue  # sin esquema del contrato → pieza aún sin cosechar
            tasas = m.get('tasas') or {}
            snaps = m.get('snapshots') or []
            ultimo = snaps[-1] if snaps else {}
            filas.append({
                'semana': p.semana_inicio.strftime('%d-%m'),
                'pieza': p.pieza_key,
                'canal': p.canal,
                'titulo': (p.titulo or '')[:80],
                'valiosa': float(tasas.get('valiosa') or 0),
                'reach': int(ultimo.get('reach') or 0),
                'saves': int(ultimo.get('saves') or 0),
                'shares': int(ultimo.get('shares') or 0),
            })
            flag = caption_sin_editar(_caption_generado(p), m.get('caption_publicado'))
            if flag is not None:
                sin_editar_flags.append(flag)

        if not filas:
            return ''

        filas.sort(key=lambda f: (f['valiosa'], f['reach']), reverse=True)
        top = filas[:3]
        bottom = list(reversed(filas[3:][-3:]))  # peores primero, sin solaparse con el top

        lineas = [
            f'=== MÉTRICAS REALES POR PUBLICACIÓN (últimas {semanas} semanas, cosecha Instagram) ===',
            'Ranking por "tasa valiosa" = (guardados+compartidos)/alcance. Jerarquía de decisión:',
            'consultas/ventas > guardados+compartidos > alcance > likes (consultas/ventas aún SIN fuente — no inventar proxies).',
            'OJO: publicaciones más antiguas acumulan más días de exposición — comparar con criterio.',
            '',
            'LO QUE MEJOR FUNCIONÓ:',
        ]
        lineas.extend(_fmt_fila(f) for f in top)
        if bottom:
            lineas.append('')
            lineas.append('LO QUE PEOR FUNCIONÓ:')
            lineas.extend(_fmt_fila(f) for f in bottom)
        if sin_editar_flags:
            ok = sum(1 for x in sin_editar_flags if x)
            pct = 100.0 * ok / len(sin_editar_flags)
            lineas.append('')
            lineas.append(
                f'META-MÉTRICA DEL APRENDIZAJE: {pct:.0f}% de los captions se publicaron sin editar '
                f'({ok}/{len(sin_editar_flags)} evaluables). Objetivo: que SUBA semana a semana '
                '(el sistema va aprendiendo la voz y la CM corrige cada vez menos).'
            )
        lineas.append('')
        lineas.append(
            'INSTRUCCIÓN: abre el brief con la sección «Decisiones de la semana» (antes de todo lo demás): '
            'PERSISTIR con los ángulos/formatos del top (di cuáles y por qué), NO INSISTIR con los del bottom '
            '(cambiar el ángulo o abandonarlo), RE-ENFOCAR lo mediocre. Cada decisión fundamentada con su dato, '
            'y los conceptos que propongas esta semana deben REFLEJAR estas decisiones.'
        )
        return '\n'.join(lineas)
    except Exception:  # noqa: BLE001 — el brief del lunes nunca se cae por métricas
        logger.exception('recolectar_decisiones falló — el brief sale sin la sección')
        return ''
