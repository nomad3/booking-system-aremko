"""
recalcular_taxonomia_clientes
=============================

Llena / actualiza la tabla ClienteTaxonomia con las 3 etiquetas
(eje_valor, eje_estilo, eje_contexto) + un snapshot de features clave
para cada cliente que tenga al menos 1 reserva en los últimos N meses
o al menos 1 registro en ServiceHistory.

Uso:
    # Primera vez (llena todos los clientes):
    python manage.py recalcular_taxonomia_clientes

    # Refresca solo los que cambiaron en las últimas 24h (cron nocturno):
    python manage.py recalcular_taxonomia_clientes --solo-modificados-desde 24h

    # Modo dry-run (no escribe a DB, solo reporta):
    python manage.py recalcular_taxonomia_clientes --dry-run

Diseño:
- Reutiliza las funciones classifier del comando exploratorio
  `analyze_customer_taxonomy` (v4) para garantizar consistencia.
- Re-implementa la agregación de features con `date` objects (no strings)
  para persistir directo a DateField sin parsing.
- Persiste usando estrategia split (bulk_create + bulk_update) para
  eficiencia: ~14K clientes se procesan en <60 segundos.
- statement_timeout 60s (en lugar de 8s) porque es un job batch que
  legítimamente puede tardar más que las queries de dashboard.
"""

from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Dict, List, Optional, Set, Tuple

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.db.models import Count, Min, Max
from django.utils import timezone

from ventas.management.commands.analyze_customer_taxonomy import (
    TIPO_TO_FAMILIA,
    FAMILIAS_CORE,
    _classify_eje_valor,
    _classify_eje_estilo,
    _classify_eje_contexto,
)
from ventas.models import (
    Cliente,
    ClienteTaxonomia,
    ReservaServicio,
    ServiceHistory,
    VentaReserva,
)


# Campos del modelo ClienteTaxonomia que el bulk_update debe refrescar
# (todos menos `cliente` y `id`). `calculado_en` se actualiza solo
# (auto_now=True) en cada bulk_update.
FIELDS_TO_UPDATE = [
    'eje_valor', 'eje_estilo', 'eje_contexto',
    'meses_ventana',
    'total_visitas', 'gasto_total', 'ticket_promedio',
    'primera_visita_actual', 'ultima_visita',
    'dias_desde_ultima_visita', 'dias_entre_visitas_avg',
    'meses_relacion_actual',
    'pct_tinas', 'pct_masajes', 'pct_cabanas', 'pct_otros',
    'gasto_tinas', 'gasto_masajes', 'gasto_cabanas', 'gasto_otros',
    'avg_cantidad_personas',
    'pct_reservas_bundle', 'count_reservas_bundle',
    'pct_finde', 'pct_verano', 'pct_otono', 'pct_invierno', 'pct_primavera',
    'tiene_historial_pre_sistema', 'visitas_history_count',
    'primera_visita_global', 'antiguedad_meses',
    'calculado_en',
]


def _season_for_month(m: int) -> str:
    """Hemisferio sur."""
    if m in (12, 1, 2):
        return 'verano'
    if m in (3, 4, 5):
        return 'otono'
    if m in (6, 7, 8):
        return 'invierno'
    return 'primavera'


def _parse_relative_duration(s: str) -> Optional[timedelta]:
    """Convierte '24h', '7d', '30m' a timedelta. None si no parsea."""
    m = re.match(r'^(\d+)([hdmHDM])$', s.strip())
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    if unit == 'h':
        return timedelta(hours=n)
    if unit == 'd':
        return timedelta(days=n)
    if unit == 'm':
        return timedelta(minutes=n)
    return None


class Command(BaseCommand):
    help = (
        "Recalcula la tabla ClienteTaxonomia con etiquetas multidimensionales "
        "+ snapshot de features. Diseñado para correr nightly como cron."
    )

    # Ventana hardcoded para producción (matchea el v4 validado).
    MESES_VENTANA = 24

    def add_arguments(self, parser):
        parser.add_argument(
            '--solo-modificados-desde', type=str, default=None,
            help=(
                'Solo recalcula clientes que tuvieron VentaReserva nueva o '
                'modificada en este período relativo (ej: 24h, 7d). '
                'Si se omite, recalcula TODOS los clientes.'
            ),
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='No escribe a DB. Solo reporta qué pasaría.',
        )
        parser.add_argument(
            '--batch-size', type=int, default=500,
            help='Tamaño de batch para bulk_create/bulk_update (default 500).',
        )
        # ──── Operación Vuelta a Casa · Etapa 5.3 ────
        # Flag opt-in para registrar TaxonomiaMovimiento + EventoCelebracion
        # cuando se detectan cambios en los ejes. Default OFF garantiza que
        # el comportamiento actual NO cambia (bit-exact) hasta que se opta in.
        parser.add_argument(
            '--registrar-movimientos', action='store_true',
            help=(
                'OPT-IN: registra TaxonomiaMovimiento + EventoCelebracion '
                'cuando detecta cambios en los ejes. Default OFF — '
                'comportamiento bit-exact al actual.'
            ),
        )
        parser.add_argument(
            '--evento-origen', type=str, default='recalculo_features',
            choices=['reserva', 'paso_tiempo', 'recalculo_features', 'manual'],
            help=(
                "Valor de evento_origen para los TaxonomiaMovimiento creados "
                "(solo aplica con --registrar-movimientos). "
                "Default 'recalculo_features'."
            ),
        )

    def handle(self, *args, **opts):
        t0 = time.time()
        dry_run = opts['dry_run']
        batch_size = opts['batch_size']
        modificados_desde_str = opts['solo_modificados_desde']
        registrar_movimientos = opts['registrar_movimientos']
        evento_origen = opts['evento_origen']

        today = timezone.now().date()
        # periodo_start = primer día del mes "hace 23 meses".
        total_meses_atras = (today.year * 12 + (today.month - 1)) - (self.MESES_VENTANA - 1)
        first_y = total_meses_atras // 12
        first_m = (total_meses_atras % 12) + 1
        periodo_start = date(first_y, first_m, 1)
        periodo_stop = today

        self.stdout.write(self.style.NOTICE(
            f"Período sistema actual: {periodo_start} → {periodo_stop} "
            f"({self.MESES_VENTANA} meses)"
        ))

        # ----- Filtro opcional: solo clientes modificados recientemente -----
        cliente_ids_filtro: Optional[Set[int]] = None
        if modificados_desde_str:
            delta = _parse_relative_duration(modificados_desde_str)
            if delta is None:
                raise CommandError(
                    f"--solo-modificados-desde inválido: '{modificados_desde_str}'. "
                    f"Formato esperado: '24h', '7d', '30m'."
                )
            corte = timezone.now() - delta
            cliente_ids_filtro = set(
                VentaReserva.objects.filter(fecha_creacion__gte=corte)
                .values_list('cliente_id', flat=True).distinct()
            )
            self.stdout.write(
                f"Filtro activo: solo clientes con VentaReserva desde {corte.isoformat()} "
                f"→ {len(cliente_ids_filtro)} clientes candidatos."
            )
            if not cliente_ids_filtro:
                self.stdout.write(self.style.SUCCESS(
                    "Nada que recalcular. Saliendo."
                ))
                return

        # ----- Statement timeout 60s para job batch -----
        with transaction.atomic():
            with connection.cursor() as cursor:
                try:
                    cursor.execute("SET LOCAL statement_timeout = '60s'")
                except Exception:
                    pass  # SQLite no soporta

            # ----- Construir features -----
            features, meta = self._build_features(
                periodo_start=periodo_start,
                periodo_stop=periodo_stop,
                today=today,
                cliente_ids_filtro=cliente_ids_filtro,
            )

            self.stdout.write(
                f"Features calculadas: {len(features):,} clientes "
                f"(sistema={len(meta['cliente_ids_sistema']):,}, "
                f"history={len(meta['cliente_ids_history']):,}, "
                f"ambos={len(meta['cliente_ids_ambos']):,})"
            )

            # ----- Clasificar -----
            for cid, f in features.items():
                f['eje_valor'] = _classify_eje_valor(f)
                f['eje_estilo'] = _classify_eje_estilo(f)
                f['eje_contexto'] = _classify_eje_contexto(f)

            # ----- Persistir -----
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    f"DRY-RUN: se omite la escritura a DB. "
                    f"Habría procesado {len(features):,} filas."
                ))
                self._print_distribution(features)
                return

            stats = self._persist(
                features,
                batch_size=batch_size,
                registrar_movimientos=registrar_movimientos,
                evento_origen=evento_origen,
            )
            elapsed = time.time() - t0
            self.stdout.write(self.style.SUCCESS(
                f"OK: {stats['created']:,} creados, {stats['updated']:,} actualizados, "
                f"{stats['unchanged']:,} sin cambios. Tiempo: {elapsed:.1f}s"
            ))
            if registrar_movimientos:
                self.stdout.write(self.style.NOTICE(
                    f"Bitácora viva: {stats['movimientos_creados']:,} movimientos, "
                    f"{stats['celebraciones_creadas']:,} celebraciones "
                    f"(evento_origen='{evento_origen}')"
                ))
            self._print_distribution(features)

    # -----------------------------------------------------------------------
    # Construcción de features por cliente (dates como `date`, no strings).
    # Misma lógica del comando exploratorio v4 pero adaptada para persistencia.
    # -----------------------------------------------------------------------
    def _build_features(
        self,
        *,
        periodo_start: date,
        periodo_stop: date,
        today: date,
        cliente_ids_filtro: Optional[Set[int]] = None,
    ) -> Tuple[Dict[int, dict], dict]:

        # 1) Clientes con VentaReserva no cancelada en período
        ventas_qs = VentaReserva.objects.filter(
            fecha_creacion__date__gte=periodo_start,
            fecha_creacion__date__lte=periodo_stop,
        ).exclude(estado_pago='cancelado').values('cliente_id')
        cliente_ids_sistema = {v['cliente_id'] for v in ventas_qs if v['cliente_id']}

        # 2) Clientes con ServiceHistory
        sh_agg = ServiceHistory.objects.values('cliente_id').annotate(
            count=Count('id'),
            primera=Min('service_date'),
        )
        sh_by_cliente: Dict[int, dict] = {
            row['cliente_id']: {
                'count': row['count'],
                'primera': row['primera'],
            }
            for row in sh_agg if row['cliente_id']
        }
        cliente_ids_history = set(sh_by_cliente.keys())

        cliente_ids_ambos = cliente_ids_sistema & cliente_ids_history
        cliente_ids_solo_history = cliente_ids_history - cliente_ids_sistema
        eligibles = cliente_ids_sistema | cliente_ids_history

        # Aplicar filtro opcional (modo cron incremental)
        if cliente_ids_filtro is not None:
            eligibles = eligibles & cliente_ids_filtro

        # 3) Aggregator por cliente
        per_cli: Dict[int, dict] = defaultdict(lambda: {
            'fechas_creacion_ventas': set(),
            'venta_ids': set(),
            'count_familia': Counter(),
            'gasto_familia': defaultdict(float),
            'max_cantidad_por_venta': {},   # vid → max(cantidad_personas)
            'fechas_agendamiento': [],
            'venta_familias': defaultdict(set),
        })

        # 4) Una query: todas las ReservaServicio del período
        rs_filter = {
            'venta_reserva__fecha_creacion__date__gte': periodo_start,
            'venta_reserva__fecha_creacion__date__lte': periodo_stop,
        }
        if cliente_ids_filtro is not None:
            rs_filter['venta_reserva__cliente_id__in'] = cliente_ids_filtro

        rs_qs = ReservaServicio.objects.filter(**rs_filter).exclude(
            venta_reserva__estado_pago='cancelado',
        ).values(
            'venta_reserva_id',
            'venta_reserva__cliente_id',
            'venta_reserva__fecha_creacion',
            'fecha_agendamiento',
            'servicio__tipo_servicio',
            'precio_unitario_venta',
            'servicio__precio_base',
            'cantidad_personas',
        )

        for row in rs_qs:
            cid = row['venta_reserva__cliente_id']
            if not cid:
                continue
            agg = per_cli[cid]
            vid = row['venta_reserva_id']
            agg['venta_ids'].add(vid)

            fc = row['venta_reserva__fecha_creacion']
            fc_d = fc.date() if hasattr(fc, 'date') else fc
            if fc_d is not None:
                agg['fechas_creacion_ventas'].add(fc_d)

            tipo = row['servicio__tipo_servicio'] or 'otro'
            if tipo not in TIPO_TO_FAMILIA:
                tipo = 'otro'
            fam = TIPO_TO_FAMILIA[tipo]
            agg['count_familia'][fam] += 1

            precio_unit = row['precio_unitario_venta']
            if precio_unit is None:
                precio_unit = row['servicio__precio_base'] or 0
            # Sanity clamp: cantidad_personas debe estar en [1, 20] para un
            # spa boutique. Valores fuera de ese rango son data legacy corrupta
            # (probablemente precios mal guardados en este campo en imports
            # antiguos: 50000, 20000, 1080000 son valores observados en BD).
            # Tratar como 1 (default) para no contaminar avg/gasto.
            cant_raw = row['cantidad_personas']
            if cant_raw is None or cant_raw <= 0 or cant_raw > 20:
                cant = 1
            else:
                cant = cant_raw
            rev = float(precio_unit) * cant
            agg['gasto_familia'][fam] += rev

            prev_max = agg['max_cantidad_por_venta'].get(vid, 0)
            if cant > prev_max:
                agg['max_cantidad_por_venta'][vid] = cant

            fa = row['fecha_agendamiento']
            if fa is not None:
                agg['fechas_agendamiento'].append(fa)

            if fam in FAMILIAS_CORE:
                agg['venta_familias'][vid].add(fam)
            else:
                agg['venta_familias'].setdefault(vid, set())

        # 5) Construir dict final por cliente (dates como objetos)
        features: Dict[int, dict] = {}
        for cid in eligibles:
            agg = per_cli.get(cid)

            if agg:
                visitas = len(agg['venta_ids'])
                count_t = agg['count_familia'].get('tinas', 0)
                count_m = agg['count_familia'].get('masajes', 0)
                count_c = agg['count_familia'].get('cabanas', 0)
                count_o = agg['count_familia'].get('otros', 0)
                total_serv = count_t + count_m + count_c + count_o

                gasto_t = round(agg['gasto_familia'].get('tinas', 0.0), 2)
                gasto_m = round(agg['gasto_familia'].get('masajes', 0.0), 2)
                gasto_c = round(agg['gasto_familia'].get('cabanas', 0.0), 2)
                gasto_o = round(agg['gasto_familia'].get('otros', 0.0), 2)
                gasto_total = round(gasto_t + gasto_m + gasto_c + gasto_o, 2)
                ticket_promedio = round(gasto_total / visitas, 2) if visitas else 0.0

                fechas = sorted(agg['fechas_creacion_ventas'])
                primera_actual = fechas[0] if fechas else None
                ultima = fechas[-1] if fechas else None
                dias_desde_ultima = (today - ultima).days if ultima else None
                if primera_actual and ultima and len(fechas) >= 2:
                    span = (ultima - primera_actual).days
                    dias_entre_avg = round(span / (len(fechas) - 1), 1)
                    meses_rel = round(span / 30, 1)
                else:
                    dias_entre_avg = None
                    meses_rel = 0.0

                if total_serv:
                    pct_t = round(count_t / total_serv * 100, 1)
                    pct_m = round(count_m / total_serv * 100, 1)
                    pct_c = round(count_c / total_serv * 100, 1)
                    pct_o = round(count_o / total_serv * 100, 1)
                else:
                    pct_t = pct_m = pct_c = pct_o = 0.0

                bundle = 0
                for vid, fams in agg['venta_familias'].items():
                    if len(fams) >= 2:
                        bundle += 1
                pct_bundle = round(bundle / visitas * 100, 1) if visitas else 0.0

                cant_list = list(agg['max_cantidad_por_venta'].values())
                if cant_list:
                    avg_cant = round(sum(cant_list) / len(cant_list), 2)
                else:
                    avg_cant = None

                fa_list = agg['fechas_agendamiento']
                if fa_list:
                    n_fa = len(fa_list)
                    finde = sum(1 for d in fa_list if d.weekday() >= 5)
                    pct_finde = round(finde / n_fa * 100, 1)
                    season_counts = Counter(_season_for_month(d.month) for d in fa_list)
                    pct_v = round(season_counts.get('verano', 0) / n_fa * 100, 1)
                    pct_ot = round(season_counts.get('otono', 0) / n_fa * 100, 1)
                    pct_inv = round(season_counts.get('invierno', 0) / n_fa * 100, 1)
                    pct_pri = round(season_counts.get('primavera', 0) / n_fa * 100, 1)
                else:
                    pct_finde = 0.0
                    pct_v = pct_ot = pct_inv = pct_pri = 0.0
            else:
                # Cliente solo en ServiceHistory (sin sistema actual)
                visitas = 0
                count_t = count_m = count_c = count_o = 0
                gasto_t = gasto_m = gasto_c = gasto_o = 0.0
                gasto_total = 0.0
                ticket_promedio = 0.0
                primera_actual = None
                ultima = None
                dias_desde_ultima = None
                dias_entre_avg = None
                meses_rel = 0.0
                pct_t = pct_m = pct_c = pct_o = 0.0
                bundle = 0
                pct_bundle = 0.0
                avg_cant = None
                pct_finde = 0.0
                pct_v = pct_ot = pct_inv = pct_pri = 0.0

            # Pre-sistema info
            sh = sh_by_cliente.get(cid)
            tiene_hist = bool(sh)
            visitas_hist = sh['count'] if sh else 0
            primera_hist = sh['primera'] if sh else None

            candidatos = [d for d in (primera_actual, primera_hist) if d is not None]
            primera_global = min(candidatos) if candidatos else None
            antiguedad_meses = round((today - primera_global).days / 30) if primera_global else 0

            features[cid] = {
                'cliente_id': cid,
                # IMPORTANTE: estos son los nombres que esperan los classifiers
                'total_visitas': visitas,
                'gasto_total': gasto_total,
                'ticket_promedio': ticket_promedio,
                'primera_visita_actual': primera_actual,
                'ultima_visita': ultima,
                'dias_desde_ultima_visita': dias_desde_ultima,
                'dias_entre_visitas_avg': dias_entre_avg,
                'meses_relacion_actual': meses_rel,
                'count_tinas': count_t, 'count_masajes': count_m,
                'count_cabanas': count_c, 'count_otros': count_o,
                'pct_tinas': pct_t, 'pct_masajes': pct_m,
                'pct_cabanas': pct_c, 'pct_otros': pct_o,
                'gasto_tinas': gasto_t, 'gasto_masajes': gasto_m,
                'gasto_cabanas': gasto_c, 'gasto_otros': gasto_o,
                'count_reservas_bundle': bundle,
                'pct_reservas_bundle': pct_bundle,
                'avg_cantidad_personas': avg_cant,
                'pct_finde': pct_finde,
                # pct_semana se infiere; los classifiers lo usan
                'pct_semana': round(100 - pct_finde, 1),
                'pct_verano': pct_v, 'pct_otono': pct_ot,
                'pct_invierno': pct_inv, 'pct_primavera': pct_pri,
                'tiene_historial_pre_sistema': tiene_hist,
                'visitas_history_count': visitas_hist,
                'primera_visita_global': primera_global,
                'antiguedad_meses': antiguedad_meses,
            }

        meta = {
            'cliente_ids_sistema': cliente_ids_sistema,
            'cliente_ids_history': cliente_ids_history,
            'cliente_ids_ambos': cliente_ids_ambos,
            'cliente_ids_solo_history': cliente_ids_solo_history,
        }
        return features, meta

    # -----------------------------------------------------------------------
    # Persistencia: split create+update para eficiencia
    # -----------------------------------------------------------------------
    def _persist(
        self,
        features: Dict[int, dict],
        batch_size: int,
        registrar_movimientos: bool = False,
        evento_origen: str = 'recalculo_features',
    ) -> dict:
        # 1) IDs ya en la tabla
        existing = {
            t.cliente_id: t
            for t in ClienteTaxonomia.objects.filter(
                cliente_id__in=list(features.keys())
            )
        }

        to_create: List[ClienteTaxonomia] = []
        to_update: List[ClienteTaxonomia] = []
        unchanged = 0

        # ──── Etapa 5.3: capturar snapshots para Bitácora Viva ────
        # Solo si flag opt-in. Si OFF, esta lista queda vacía y todo el bloque
        # de registro al final se skipea → comportamiento bit-exact al previo.
        # Cada entrada: (cliente_id, antes_dict | None, despues_dict)
        snapshots_para_movimientos: List[Tuple[int, Optional[dict], dict]] = []

        for cid, f in features.items():
            data = self._features_to_model_kwargs(f)
            inst = existing.get(cid)

            # Capturar 3 ejes ANTES de modificar (solo si vamos a registrar)
            antes_ejes = None
            if registrar_movimientos and inst is not None:
                antes_ejes = {
                    'eje_valor': inst.eje_valor,
                    'eje_estilo': inst.eje_estilo,
                    'eje_contexto': inst.eje_contexto,
                }

            if inst is None:
                obj = ClienteTaxonomia(cliente_id=cid, **data)
                to_create.append(obj)
                if registrar_movimientos:
                    # Cliente nuevo: anterior=None, generar_movimientos_y_celebraciones
                    # creará el movimiento como "creación inicial" sin celebraciones.
                    snapshots_para_movimientos.append((cid, None, data))
            else:
                changed = False
                for k, v in data.items():
                    if getattr(inst, k) != v:
                        setattr(inst, k, v)
                        changed = True
                if changed:
                    to_update.append(inst)
                    if registrar_movimientos:
                        snapshots_para_movimientos.append((cid, antes_ejes, data))
                else:
                    unchanged += 1

        # 2) bulk_create
        if to_create:
            ClienteTaxonomia.objects.bulk_create(to_create, batch_size=batch_size)

        # 3) bulk_update
        if to_update:
            # No incluimos calculado_en aquí — auto_now lo maneja al save() pero
            # bulk_update lo bypassea, así que lo seteamos manualmente.
            now = timezone.now()
            for inst in to_update:
                inst.calculado_en = now
            ClienteTaxonomia.objects.bulk_update(
                to_update, FIELDS_TO_UPDATE, batch_size=batch_size
            )

        # ──── Etapa 5.3: registrar movimientos + celebraciones ────
        # Solo entra si flag --registrar-movimientos. Si OFF, snapshots_para_movimientos
        # está vacío y todo este bloque se skipea (cero overhead).
        movimientos_creados = 0
        celebraciones_creadas = 0
        if registrar_movimientos and snapshots_para_movimientos:
            from ventas.models import Cliente
            from ventas.services.taxonomia_movimientos_service import (
                generar_movimientos_y_celebraciones,
            )

            # Optimización: cargar todos los Cliente involucrados de una vez
            cliente_ids_movimiento = [s[0] for s in snapshots_para_movimientos]
            clientes = {
                c.id: c for c in Cliente.objects.filter(id__in=cliente_ids_movimiento)
            }

            for cid, antes_dict, despues_dict in snapshots_para_movimientos:
                cli = clientes.get(cid)
                if cli is None:
                    # Cliente borrado entre que cargamos features y ahora
                    # (extremadamente raro pero defensivo)
                    continue
                mov, celebs = generar_movimientos_y_celebraciones(
                    cliente=cli,
                    taxo_anterior=antes_dict,
                    taxo_nuevo=despues_dict,
                    evento_origen=evento_origen,
                )
                if mov is not None:
                    movimientos_creados += 1
                celebraciones_creadas += len(celebs)

        return {
            'created': len(to_create),
            'updated': len(to_update),
            'unchanged': unchanged,
            'movimientos_creados': movimientos_creados,
            'celebraciones_creadas': celebraciones_creadas,
        }

    @staticmethod
    def _features_to_model_kwargs(f: dict) -> dict:
        """Mapea el dict de features al subset de campos del modelo."""
        return {
            'eje_valor': f['eje_valor'],
            'eje_estilo': f['eje_estilo'],
            'eje_contexto': f['eje_contexto'],
            'meses_ventana': Command.MESES_VENTANA,
            'total_visitas': f['total_visitas'],
            'gasto_total': int(f['gasto_total']),
            'ticket_promedio': int(f['ticket_promedio']),
            'primera_visita_actual': f['primera_visita_actual'],
            'ultima_visita': f['ultima_visita'],
            'dias_desde_ultima_visita': f['dias_desde_ultima_visita'],
            'dias_entre_visitas_avg': f['dias_entre_visitas_avg'],
            'meses_relacion_actual': f['meses_relacion_actual'],
            'pct_tinas': f['pct_tinas'], 'pct_masajes': f['pct_masajes'],
            'pct_cabanas': f['pct_cabanas'], 'pct_otros': f['pct_otros'],
            'gasto_tinas': int(f['gasto_tinas']),
            'gasto_masajes': int(f['gasto_masajes']),
            'gasto_cabanas': int(f['gasto_cabanas']),
            'gasto_otros': int(f['gasto_otros']),
            'avg_cantidad_personas': f['avg_cantidad_personas'],
            'pct_reservas_bundle': f['pct_reservas_bundle'],
            'count_reservas_bundle': f['count_reservas_bundle'],
            'pct_finde': f['pct_finde'],
            'pct_verano': f['pct_verano'], 'pct_otono': f['pct_otono'],
            'pct_invierno': f['pct_invierno'], 'pct_primavera': f['pct_primavera'],
            'tiene_historial_pre_sistema': f['tiene_historial_pre_sistema'],
            'visitas_history_count': f['visitas_history_count'],
            'primera_visita_global': f['primera_visita_global'],
            'antiguedad_meses': f['antiguedad_meses'],
        }

    # -----------------------------------------------------------------------
    # Reporte de distribución (al final, para confirmar resultados)
    # -----------------------------------------------------------------------
    def _print_distribution(self, features: Dict[int, dict]):
        total = len(features)
        if total == 0:
            return
        n_pre = sum(1 for f in features.values() if f['eje_valor'] == 'Pre-sistema')
        n_sa = total - n_pre

        self.stdout.write("")
        self.stdout.write(self.style.NOTICE(f"Distribución sobre {total:,} clientes procesados:"))
        self.stdout.write(f"  Sistema actual: {n_sa:,} | Pre-sistema: {n_pre:,}")

        for eje_name, key in [('Valor', 'eje_valor'), ('Estilo', 'eje_estilo'), ('Contexto', 'eje_contexto')]:
            counter = Counter(f[key] for f in features.values())
            self.stdout.write(f"  Eje {eje_name}:")
            for label, n in counter.most_common():
                pct = n / total * 100
                self.stdout.write(f"    {label:>30s}: {n:>5,} ({pct:5.1f}%)")
