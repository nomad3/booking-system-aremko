"""
analizar_pareja_romantica
=========================

Comando read-only para diagnosticar la sub-clasificación de "Pareja Romántica"
en ClienteTaxonomia.eje_contexto.

Hoy solo 24 clientes (0.6%) son "Pareja Romántica" vs 2.381 (61.1%) "Visitante
Pareja". Hipótesis: la heurística no cruza con servicios/productos de
ambientación romántica en el historial.

Este reporte identifica:
  1. Servicios románticos (Ambientaciones + nombre con "romántic*")
  2. Productos románticos (nombre con "romántic*" o "ambient*+romántic*")
  3. Clientes únicos con esos servicios/productos en su historial
  4. Cross-tab con eje_contexto actual (cuántos son Visitante Pareja → mover)
  5. Cross-tab con eje_valor (perfil de valor de los románticos)
  6. Top 50 candidatos para re-clasificar

NO escribe a BD. NO altera estado. Solo SELECT + agregaciones + print.

Uso:
    python manage.py analizar_pareja_romantica
    python manage.py analizar_pareja_romantica --json
"""

from __future__ import annotations

import json as json_lib
from collections import Counter
from typing import Dict, List, Set

from django.core.management.base import BaseCommand
from django.db.models import Count, Q, Sum

from ventas.models import (
    Cliente,
    ClienteTaxonomia,
    Producto,
    ReservaProducto,
    ReservaServicio,
    Servicio,
)


class Command(BaseCommand):
    help = (
        "Analiza la cobertura de 'Pareja Romántica' en ClienteTaxonomia.eje_contexto "
        "cruzando con historial de servicios/productos de ambientación romántica. "
        "Read-only — no escribe a BD."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--json', action='store_true',
            help='Output en JSON (parseable) en lugar de tabla legible.',
        )
        parser.add_argument(
            '--top-candidatos', type=int, default=50,
            help='Cantidad de clientes candidatos a listar (default 50).',
        )

    def handle(self, *args, **opts):
        json_output = opts['json']
        top_n = opts['top_candidatos']

        reporte = self._construir_reporte(top_n)

        if json_output:
            self.stdout.write(json_lib.dumps(reporte, ensure_ascii=False, indent=2, default=str))
        else:
            self._imprimir_tabla(reporte)

    # ====================================================================
    # Identificación de servicios/productos románticos
    # ====================================================================

    def _identificar_servicios_romanticos(self) -> List[dict]:
        """Servicios con categoria='Ambientaciones' OR nombre con 'romántic*'.

        Devuelve lista de dicts con id, nombre, categoria_nombre, count_reservas.
        """
        # Q combinado: ambientaciones (catch-all confirmado) + variantes nombre
        filtro = (
            Q(categoria__nombre__icontains='ambient')
            | Q(nombre__icontains='romántic')
            | Q(nombre__icontains='romantic')
        )
        servicios = (
            Servicio.objects
            .filter(filtro)
            .annotate(count_reservas=Count('reservaservicio'))
            .order_by('-count_reservas')
            .values('id', 'nombre', 'categoria__nombre', 'count_reservas')
        )
        return list(servicios)

    def _identificar_productos_romanticos(self) -> List[dict]:
        """Productos con nombre que matchee romántic* o ambient* + romántic*."""
        filtro = (
            Q(nombre__icontains='romántic')
            | Q(nombre__icontains='romantic')
            # Para nombres como "Ambientación Romántica" o variantes
            | (Q(nombre__icontains='ambient') & (
                Q(nombre__icontains='romántic') | Q(nombre__icontains='romantic')
            ))
        )
        productos = (
            Producto.objects
            .filter(filtro)
            .annotate(count_ventas=Count('reservaproducto'))
            .order_by('-count_ventas')
            .values('id', 'nombre', 'count_ventas')
        )
        return list(productos)

    # ====================================================================
    # Identificación de clientes con historial romántico
    # ====================================================================

    def _clientes_con_historial_romantico(
        self, servicio_ids: List[int], producto_ids: List[int]
    ) -> Set[int]:
        """Cliente IDs únicos con al menos 1 reserva o venta de los anteriores."""
        cliente_ids = set()

        if servicio_ids:
            cliente_ids.update(
                ReservaServicio.objects
                .filter(servicio_id__in=servicio_ids)
                .values_list('venta_reserva__cliente_id', flat=True)
                .distinct()
            )
        if producto_ids:
            cliente_ids.update(
                ReservaProducto.objects
                .filter(producto_id__in=producto_ids)
                .values_list('venta_reserva__cliente_id', flat=True)
                .distinct()
            )

        cliente_ids.discard(None)
        return cliente_ids

    # ====================================================================
    # Cross-tabs y top candidatos
    # ====================================================================

    def _cross_tab_eje_contexto(self, cliente_ids: Set[int]) -> Dict[str, int]:
        """Cuántos de esos clientes están en cada eje_contexto."""
        if not cliente_ids:
            return {}
        return dict(
            ClienteTaxonomia.objects
            .filter(cliente_id__in=cliente_ids)
            .values('eje_contexto')
            .annotate(n=Count('id'))
            .values_list('eje_contexto', 'n')
        )

    def _cross_tab_eje_valor(self, cliente_ids: Set[int]) -> Dict[str, int]:
        if not cliente_ids:
            return {}
        return dict(
            ClienteTaxonomia.objects
            .filter(cliente_id__in=cliente_ids)
            .values('eje_valor')
            .annotate(n=Count('id'))
            .values_list('eje_valor', 'n')
        )

    def _top_candidatos_a_reclasificar(
        self, servicio_ids: List[int], producto_ids: List[int], top_n: int,
    ) -> List[dict]:
        """Top clientes que tienen historial romántico Y están como
        'Visitante Pareja' actualmente — candidatos prioritarios a mover.

        Ordenamos por gasto_total DESC (los más valiosos primero).
        """
        # Contar ocurrencias por cliente: cuántas reservas/ventas románticas tiene
        contador: Counter = Counter()

        if servicio_ids:
            qs_rs = (
                ReservaServicio.objects
                .filter(servicio_id__in=servicio_ids)
                .values('venta_reserva__cliente_id')
                .annotate(c=Count('id'))
                .values_list('venta_reserva__cliente_id', 'c')
            )
            for cid, c in qs_rs:
                if cid:
                    contador[cid] += c
        if producto_ids:
            qs_rp = (
                ReservaProducto.objects
                .filter(producto_id__in=producto_ids)
                .values('venta_reserva__cliente_id')
                .annotate(c=Count('id'))
                .values_list('venta_reserva__cliente_id', 'c')
            )
            for cid, c in qs_rp:
                if cid:
                    contador[cid] += c

        if not contador:
            return []

        # Filtrar solo los que son 'Visitante Pareja' actualmente
        cliente_ids_visitante_pareja = set(
            ClienteTaxonomia.objects
            .filter(
                cliente_id__in=contador.keys(),
                eje_contexto='Visitante Pareja',
            )
            .values_list('cliente_id', flat=True)
        )

        # Cargar info de los candidatos
        candidatos_qs = (
            ClienteTaxonomia.objects
            .filter(cliente_id__in=cliente_ids_visitante_pareja)
            .select_related('cliente')
            .order_by('-gasto_total')
            .values(
                'cliente_id', 'cliente__nombre', 'cliente__telefono',
                'eje_valor', 'eje_estilo', 'gasto_total', 'total_visitas',
            )
        )

        out = []
        for row in candidatos_qs[:top_n]:
            out.append({
                **row,
                'count_romantico': contador.get(row['cliente_id'], 0),
            })
        return out

    # ====================================================================
    # Construir el reporte completo
    # ====================================================================

    def _construir_reporte(self, top_n: int) -> dict:
        servicios = self._identificar_servicios_romanticos()
        productos = self._identificar_productos_romanticos()
        servicio_ids = [s['id'] for s in servicios]
        producto_ids = [p['id'] for p in productos]

        cliente_ids_romanticos = self._clientes_con_historial_romantico(
            servicio_ids, producto_ids,
        )

        total_clientes = Cliente.objects.count()
        total_taxonomia = ClienteTaxonomia.objects.count()

        cross_contexto = self._cross_tab_eje_contexto(cliente_ids_romanticos)
        cross_valor = self._cross_tab_eje_valor(cliente_ids_romanticos)

        top_candidatos = self._top_candidatos_a_reclasificar(
            servicio_ids, producto_ids, top_n,
        )

        # Baseline de eje_contexto sobre toda la base (para comparar)
        baseline_contexto = dict(
            ClienteTaxonomia.objects
            .values('eje_contexto')
            .annotate(n=Count('id'))
            .values_list('eje_contexto', 'n')
        )

        return {
            'totales': {
                'clientes_total': total_clientes,
                'taxonomia_total': total_taxonomia,
                'clientes_con_historial_romantico': len(cliente_ids_romanticos),
            },
            'servicios_romanticos': servicios,
            'productos_romanticos': productos,
            'baseline_eje_contexto': baseline_contexto,
            'cross_tab_eje_contexto_de_romanticos': cross_contexto,
            'cross_tab_eje_valor_de_romanticos': cross_valor,
            'top_candidatos_a_reclasificar': top_candidatos,
            'top_solicitado': top_n,
        }

    # ====================================================================
    # Tabla legible
    # ====================================================================

    def _imprimir_tabla(self, r: dict):
        out = self.stdout
        SEP = '=' * 78
        SUB = '-' * 78

        out.write('')
        out.write(SEP)
        out.write('ANÁLISIS RE-CLASIFICACIÓN "Pareja Romántica" · Etapa 1 (read-only)')
        out.write(SEP)
        out.write('')

        # ---- Totales ----
        t = r['totales']
        out.write('1. TOTALES')
        out.write(SUB)
        out.write(f"  Clientes total:                       {t['clientes_total']:>6}")
        out.write(f"  Filas ClienteTaxonomia:               {t['taxonomia_total']:>6}")
        out.write(f"  Clientes con historial romántico:     {t['clientes_con_historial_romantico']:>6}")
        out.write('')

        # ---- Servicios románticos ----
        out.write(f'2. SERVICIOS ROMÁNTICOS DETECTADOS ({len(r["servicios_romanticos"])} servicios)')
        out.write(SUB)
        out.write(f"  {'count':>6}  {'id':>5}  servicio (categoría)")
        for s in r['servicios_romanticos'][:30]:
            cat = s['categoria__nombre'] or '(sin categoría)'
            out.write(f"  {s['count_reservas']:>6}  {s['id']:>5}  {s['nombre']} ({cat})")
        if len(r['servicios_romanticos']) > 30:
            out.write(f"  ... + {len(r['servicios_romanticos']) - 30} servicios más")
        out.write('')

        # ---- Productos románticos ----
        out.write(f'3. PRODUCTOS ROMÁNTICOS DETECTADOS ({len(r["productos_romanticos"])} productos)')
        out.write(SUB)
        out.write(f"  {'count':>6}  {'id':>5}  producto")
        for p in r['productos_romanticos'][:30]:
            out.write(f"  {p['count_ventas']:>6}  {p['id']:>5}  {p['nombre']}")
        if len(r['productos_romanticos']) > 30:
            out.write(f"  ... + {len(r['productos_romanticos']) - 30} productos más")
        out.write('')

        # ---- Cross-tab eje_contexto ----
        out.write('4. CROSS-TAB: eje_contexto ACTUAL de los clientes románticos')
        out.write(SUB)
        out.write(f"  {'count':>6}  eje_contexto actual")
        for ctx, n in sorted(r['cross_tab_eje_contexto_de_romanticos'].items(), key=lambda kv: -kv[1]):
            out.write(f"  {n:>6}  {ctx}")
        out.write('')
        out.write('  Baseline (TODO ClienteTaxonomia, no solo románticos):')
        for ctx, n in sorted(r['baseline_eje_contexto'].items(), key=lambda kv: -kv[1]):
            pct = (n / r['totales']['taxonomia_total'] * 100) if r['totales']['taxonomia_total'] else 0
            out.write(f"    {ctx:<28} {n:>5} ({pct:.1f}%)")
        out.write('')

        # ---- Cross-tab eje_valor ----
        out.write('5. CROSS-TAB: eje_valor de los clientes románticos')
        out.write(SUB)
        out.write(f"  {'count':>6}  eje_valor")
        for valor, n in sorted(r['cross_tab_eje_valor_de_romanticos'].items(), key=lambda kv: -kv[1]):
            out.write(f"  {n:>6}  {valor}")
        out.write('')

        # ---- Top candidatos ----
        out.write(f'6. TOP {r["top_solicitado"]} CANDIDATOS A RE-CLASIFICAR')
        out.write(SUB)
        out.write('  (clientes con historial romántico Y actualmente "Visitante Pareja")')
        out.write(f"  {'#roman':>6}  {'id':>5}  {'valor':<14}  {'estilo':<22}  {'gasto':>10}  {'visitas':>3}  nombre")
        for c in r['top_candidatos_a_reclasificar']:
            nombre = (c['cliente__nombre'] or '')[:35]
            out.write(
                f"  {c['count_romantico']:>6}  {c['cliente_id']:>5}  "
                f"{c['eje_valor']:<14}  {c['eje_estilo']:<22}  "
                f"${c['gasto_total']:>9,}  {c['total_visitas']:>3}  {nombre}"
            )
        out.write('')
        out.write(SEP)
        out.write('FIN DEL REPORTE')
        out.write(SEP)
