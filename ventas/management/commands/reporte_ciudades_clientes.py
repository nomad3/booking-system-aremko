"""
reporte_ciudades_clientes
=========================

Comando read-only de diagnóstico para Operación Vuelta a Casa · Etapa Geo.1.

Reporta cobertura del campo `ciudad` en `Cliente` y cruza con
`ClienteTaxonomia` para identificar el alcance del problema antes de
construir el modelo `Ciudad` + normalización fuzzy (Etapa Geo.2).

Uso:
    python manage.py reporte_ciudades_clientes
    python manage.py reporte_ciudades_clientes --json

NO escribe a BD. NO altera estado. Solo SELECT + agregaciones + print.

Tiempo esperado: <5 segundos sobre 14.228 clientes.
"""

from __future__ import annotations

import json as json_lib
import re
from collections import Counter
from typing import Dict, List

from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from ventas.models import Cliente, ClienteTaxonomia


# Marcadores textuales de país extranjero (búsqueda case-insensitive en ciudad)
# Solo lista mínima para conteo informativo en este reporte; la lista completa
# se decide en Etapa Geo.2 seed.
MARCADORES_EXTRANJERO = [
    'argentina', 'brasil', 'brazil', 'uruguay', 'peru', 'perú', 'bolivia',
    'colombia', 'ecuador', 'usa', 'eeuu', 'ee.uu', 'estados unidos',
    'mexico', 'méxico', 'españa', 'spain', 'francia', 'france',
    'alemania', 'germany', 'italia', 'italy', 'inglaterra', 'uk',
    'buenos aires', 'mendoza', 'sao paulo', 'são paulo', 'rio de janeiro',
    'lima', 'madrid', 'barcelona', 'paris', 'london', 'miami', 'new york',
]


def _normalizar_ciudad_para_conteo(texto: str) -> str:
    """Normaliza ciudad para agregación: lower + trim + collapse espacios."""
    if not texto:
        return ''
    s = texto.strip().lower()
    # Colapsar espacios múltiples a uno
    s = re.sub(r'\s+', ' ', s)
    return s


def _es_telefono_fijo_chile(telefono: str) -> bool:
    """Detecta si el teléfono es un fijo chileno (NO empieza con +569).

    Móviles chilenos: +569XXXXXXXX
    Fijos chilenos:   +56[X]XXXXXXX donde X=código de área (2=Santiago,
                      32=Valpo, 41=Concepción, 63=Valdivia, 64=Osorno,
                      65=Puerto Montt/Varas, etc.)
    """
    if not telefono:
        return False
    t = telefono.strip().replace(' ', '')
    # Tiene que empezar con +56 (Chile)
    if not t.startswith('+56'):
        return False
    # Después del +56, si el primer dígito es 9 → móvil; si no → fijo
    resto = t[3:]
    if not resto:
        return False
    return not resto.startswith('9')


def _es_extranjero_por_texto(texto: str) -> bool:
    """True si el texto contiene algún marcador inequívoco de país no-Chile."""
    if not texto:
        return False
    s = texto.lower()
    return any(m in s for m in MARCADORES_EXTRANJERO)


class Command(BaseCommand):
    help = "Reporta cobertura geográfica de clientes (Etapa Geo.1, read-only)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--json', action='store_true',
            help='Output en JSON (parseable) en lugar de tabla legible.',
        )
        parser.add_argument(
            '--top-ciudades', type=int, default=80,
            help='Cantidad de variantes únicas de ciudad a listar (default 80).',
        )

    def handle(self, *args, **opts):
        json_output = opts['json']
        top_n = opts['top_ciudades']

        reporte = self._construir_reporte(top_n)

        if json_output:
            self.stdout.write(json_lib.dumps(reporte, ensure_ascii=False, indent=2))
        else:
            self._imprimir_tabla(reporte)

    # ====================================================================
    # Construcción del reporte
    # ====================================================================

    def _construir_reporte(self, top_n: int) -> dict:
        # ---- Cobertura general ----
        total = Cliente.objects.count()

        # ciudad: no null AND no vacío AND no solo espacios
        con_ciudad_qs = Cliente.objects.exclude(
            Q(ciudad__isnull=True) | Q(ciudad__exact='')
        ).extra(where=["TRIM(ciudad) != ''"])  # acomoda espacios solos
        con_ciudad = con_ciudad_qs.count()

        con_comuna = Cliente.objects.exclude(comuna__isnull=True).count()
        con_region = Cliente.objects.exclude(region__isnull=True).count()
        con_pais = Cliente.objects.exclude(
            Q(pais__isnull=True) | Q(pais__exact='')
        ).count()

        # Sin ciudad PERO con comuna (potencial inferencia)
        sin_ciudad_con_comuna = Cliente.objects.filter(
            Q(ciudad__isnull=True) | Q(ciudad__exact='')
        ).exclude(comuna__isnull=True).count()

        # Sin ciudad PERO con region
        sin_ciudad_con_region = Cliente.objects.filter(
            Q(ciudad__isnull=True) | Q(ciudad__exact='')
        ).filter(comuna__isnull=True).exclude(region__isnull=True).count()

        # Teléfonos fijos (potencial pista geográfica)
        fijos = 0
        for tel in Cliente.objects.values_list('telefono', flat=True).iterator():
            if _es_telefono_fijo_chile(tel):
                fijos += 1

        # País no-Chile explícito
        no_chile = Cliente.objects.exclude(
            Q(pais__isnull=True) | Q(pais__exact='') | Q(pais__iexact='chile')
            | Q(pais__iexact='cl')
        ).count()

        # ---- Top N variantes únicas de ciudad ----
        contador = Counter()
        for ciudad in con_ciudad_qs.values_list('ciudad', flat=True).iterator():
            normalizada = _normalizar_ciudad_para_conteo(ciudad)
            if normalizada:
                contador[normalizada] += 1
        top_ciudades = contador.most_common(top_n)
        total_variantes = len(contador)
        resto_variantes = max(0, total_variantes - top_n)
        # Cuántos clientes están en el "resto" (variantes con baja frecuencia)
        clientes_en_resto = sum(
            n for _, n in contador.most_common()[top_n:]
        )

        # ---- Heurística extranjero por texto en ciudad ----
        extranjero_por_texto = 0
        for ciudad in con_ciudad_qs.values_list('ciudad', flat=True).iterator():
            if _es_extranjero_por_texto(ciudad):
                extranjero_por_texto += 1

        # ---- Cruce con ClienteTaxonomia ----
        tax_total = ClienteTaxonomia.objects.count()
        # Sin ciudad por eje_valor
        sin_ciudad_por_valor = dict(
            ClienteTaxonomia.objects
            .filter(Q(cliente__ciudad__isnull=True) | Q(cliente__ciudad__exact=''))
            .values('eje_valor').annotate(n=Count('id'))
            .values_list('eje_valor', 'n')
        )

        # Top 10 Leales/Campeones sin ciudad
        top_lc_sin_ciudad = list(
            ClienteTaxonomia.objects
            .filter(
                eje_valor__in=('Leal', 'Campeón'),
            )
            .filter(Q(cliente__ciudad__isnull=True) | Q(cliente__ciudad__exact=''))
            .select_related('cliente')
            .order_by('-gasto_total')[:10]
            .values('cliente_id', 'cliente__nombre', 'eje_valor',
                    'gasto_total', 'total_visitas')
        )

        return {
            'cobertura_general': {
                'total_clientes': total,
                'con_ciudad': con_ciudad,
                'con_comuna': con_comuna,
                'con_region': con_region,
                'con_pais': con_pais,
                'sin_ciudad_con_comuna': sin_ciudad_con_comuna,
                'sin_ciudad_con_region': sin_ciudad_con_region,
                'pct_cobertura_ciudad': round(con_ciudad / total * 100, 1) if total else 0,
                'pct_cobertura_comuna': round(con_comuna / total * 100, 1) if total else 0,
                'pct_cobertura_region': round(con_region / total * 100, 1) if total else 0,
            },
            'heuristicas_geo': {
                'telefonos_fijos_chile': fijos,
                'pais_distinto_chile': no_chile,
                'ciudad_con_marcador_extranjero': extranjero_por_texto,
            },
            'variantes_ciudad': {
                'total_variantes_unicas': total_variantes,
                'top_n_solicitado': top_n,
                'top_ciudades': [
                    {'ciudad_normalizada': c, 'count': n}
                    for c, n in top_ciudades
                ],
                'variantes_restantes': resto_variantes,
                'clientes_en_variantes_restantes': clientes_en_resto,
            },
            'cruce_taxonomia': {
                'total_taxonomia': tax_total,
                'sin_ciudad_por_eje_valor': sin_ciudad_por_valor,
                'top10_leales_campeones_sin_ciudad': list(top_lc_sin_ciudad),
            },
        }

    # ====================================================================
    # Tabla legible
    # ====================================================================

    def _imprimir_tabla(self, r: dict):
        out = self.stdout
        SEP = '=' * 70
        SUB = '-' * 70

        out.write('')
        out.write(SEP)
        out.write('REPORTE DE COBERTURA GEOGRÁFICA DE CLIENTES · Etapa Geo.1')
        out.write(SEP)
        out.write('')

        # ---- Cobertura general ----
        c = r['cobertura_general']
        out.write('1. COBERTURA GENERAL')
        out.write(SUB)
        out.write(f"  Total clientes:                {c['total_clientes']:>6}")
        out.write(f"  Con ciudad poblada:            {c['con_ciudad']:>6}  ({c['pct_cobertura_ciudad']:.1f}%)")
        out.write(f"  Con comuna (FK):               {c['con_comuna']:>6}  ({c['pct_cobertura_comuna']:.1f}%)")
        out.write(f"  Con region (FK):               {c['con_region']:>6}  ({c['pct_cobertura_region']:.1f}%)")
        out.write(f"  Con país:                      {c['con_pais']:>6}")
        out.write('')
        out.write('  Inferencia disponible:')
        out.write(f"    Sin ciudad pero con comuna:  {c['sin_ciudad_con_comuna']:>6} ← podemos inferir de comuna.nombre")
        out.write(f"    Sin ciudad/comuna con region: {c['sin_ciudad_con_region']:>6} ← solo región, menos preciso")
        out.write('')

        # ---- Heurísticas geo ----
        h = r['heuristicas_geo']
        out.write('2. HEURÍSTICAS GEOGRÁFICAS DISPONIBLES')
        out.write(SUB)
        out.write(f"  Teléfonos fijos chilenos:           {h['telefonos_fijos_chile']:>6}  (sin +569 — código de área da pista regional)")
        out.write(f"  País explícito != Chile:            {h['pais_distinto_chile']:>6}  (campo pais)")
        out.write(f"  Ciudad con marcador extranjero:     {h['ciudad_con_marcador_extranjero']:>6}  (ej. 'Buenos Aires', 'Mendoza', etc.)")
        out.write('')

        # ---- Variantes de ciudad ----
        v = r['variantes_ciudad']
        out.write(f'3. TOP {v["top_n_solicitado"]} VARIANTES ÚNICAS DE CIUDAD '
                  f'(total únicas: {v["total_variantes_unicas"]})')
        out.write(SUB)
        for item in v['top_ciudades']:
            out.write(f"  {item['count']:>5}  {item['ciudad_normalizada']}")
        if v['variantes_restantes'] > 0:
            out.write(SUB)
            out.write(
                f"  (... + {v['variantes_restantes']} variantes más con "
                f"{v['clientes_en_variantes_restantes']} clientes en total)"
            )
        out.write('')

        # ---- Cruce taxonomía ----
        t = r['cruce_taxonomia']
        out.write(f'4. CRUCE CON ClienteTaxonomia (total {t["total_taxonomia"]} filas)')
        out.write(SUB)
        out.write('  Clientes SIN ciudad por eje_valor:')
        for valor, n in sorted(t['sin_ciudad_por_eje_valor'].items(),
                                key=lambda kv: -kv[1]):
            out.write(f"    {valor:<28} {n:>5}")
        out.write('')
        out.write('  TOP 10 Leales/Campeones SIN ciudad (arregla manual prioritario):')
        for cli in t['top10_leales_campeones_sin_ciudad']:
            out.write(
                f"    [{cli['eje_valor']:<8}] cliente_id={cli['cliente_id']:>5}  "
                f"{cli['cliente__nombre'][:35]:<35}  "
                f"gasto=${cli['gasto_total']:>10,}  visitas={cli['total_visitas']}"
            )
        out.write('')
        out.write(SEP)
        out.write('FIN DEL REPORTE')
        out.write(SEP)
