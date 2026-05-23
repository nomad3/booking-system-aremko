"""
analyze_customer_taxonomy
=========================

Comando exploratorio one-shot para validar una taxonomía multidimensional
de clientes (Valor + Estilo + Contexto) ANTES de implementar persistencia.

Uso:
    python manage.py analyze_customer_taxonomy --months 24 \
        --output-dir /tmp/aremko_taxonomy/

Outputs:
    <output-dir>/taxonomy_data.csv     # 1 fila por cliente con todas las features
    <output-dir>/taxonomy_report.md    # reporte estadístico con distribuciones,
                                       # matrices cruzadas, top clientes y alertas

Notas de diseño:
- Los 3 ejes (Valor, Estilo, Contexto) se calculan SOLO con datos del sistema
  actual (últimos N meses) para que la taxonomía sea consistente. Los features
  de ServiceHistory son contextuales (antigüedad, historial pre-sistema) y NO
  entran en la clasificación.
- ServiceHistory ya tiene FK directo a Cliente (cliente_id), no se necesita
  match por teléfono/RUT.
- El CSV no incluye PII (nombre, teléfono, email, RUT). Solo cliente_id.
- Una sola pasada de queries (4-5 queries totales) + agregación en Python.
  Cap de 36 meses garantiza performance acotada.
"""

from __future__ import annotations

import csv
import os
import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Dict, List, Optional, Set, Tuple

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Min, Max
from django.utils import timezone

from ventas.models import Cliente, ReservaServicio, ServiceHistory, VentaReserva


# ---------------------------------------------------------------------------
# Constantes de clasificación
# ---------------------------------------------------------------------------

# tipo_servicio (singular, ASCII) → familia plural usada en la taxonomía.
TIPO_TO_FAMILIA = {
    'tina': 'tinas',
    'masaje': 'masajes',
    'cabana': 'cabanas',
    'otro': 'otros',
}

# Familias "core" para clasificación de combos (excluye 'otros' que suelen ser descuentos).
FAMILIAS_CORE = ('tinas', 'masajes', 'cabanas')

# Ejes — ordenados para reportes deterministas.
EJE_VALOR_ORDEN = [
    'Campeón', 'Leal', 'Gran Gastador Ocasional', 'Regular',
    'En Prueba', 'En Riesgo', 'Dormido', 'Perdido',
]
EJE_ESTILO_ORDEN = [
    'Devoto del Masaje', 'Amante de las Tinas', 'Experiencia Completa',
    'Buscador de Alojamiento', 'Probador Esporádico',
]
EJE_CONTEXTO_ORDEN = [
    'Pareja Romántica', 'Auto-cuidado Solo', 'Grupo', 'Familiar',
    'Turista Estacional', 'Local Frecuente', 'Sin clasificar',
]

# Combinaciones de interés para el reporte (Valor × Estilo / Valor × Contexto).
TOP_COMBOS_INTERES = [
    ('Campeón', 'Devoto del Masaje'),
    ('Campeón', 'Amante de las Tinas'),
    ('Campeón', 'Experiencia Completa'),
    ('Gran Gastador Ocasional', 'Experiencia Completa'),
    ('Leal', 'Pareja Romántica'),
    ('Regular', 'Devoto del Masaje'),
    ('En Riesgo', 'Amante de las Tinas'),
    ('Dormido', 'Pareja Romántica'),
]


def _normalize_servicehistory_type(raw: str) -> str:
    """ServiceHistory.service_type llega como 'Tinas', 'Masajes', 'Cabañas', etc.
    Lo normalizamos a las mismas keys plurales ASCII usadas en el resto.
    """
    if not raw:
        return 'otros'
    t = raw.strip().lower()
    # Quitar tildes simples (cabañas → cabanas).
    t = t.replace('ñ', 'n').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
    if 'tina' in t:
        return 'tinas'
    if 'masaje' in t:
        return 'masajes'
    if 'cabana' in t:
        return 'cabanas'
    return 'otros'


def _season_for_month(m: int) -> str:
    """Hemisferio sur."""
    if m in (12, 1, 2):
        return 'verano'
    if m in (3, 4, 5):
        return 'otono'
    if m in (6, 7, 8):
        return 'invierno'
    return 'primavera'


def _classify_eje_valor(f: dict) -> str:
    """Aplica las reglas de RFM tentativas del brief."""
    visitas = f['total_visitas']
    dias = f['dias_desde_ultima_visita']
    gasto = f['gasto_total']

    # Cliente sin reservas en sistema actual → Perdido por definición.
    if visitas == 0 or dias is None:
        return 'Perdido'

    if visitas >= 8 and dias <= 90 and gasto >= 500_000:
        return 'Campeón'
    if visitas >= 6 and dias <= 120:
        return 'Leal'
    if gasto >= 500_000 and visitas <= 4:
        return 'Gran Gastador Ocasional'
    if visitas >= 3 and dias <= 180:
        return 'Regular'
    if visitas <= 2 and dias <= 90:
        return 'En Prueba'
    if visitas >= 3 and 180 < dias <= 365:
        return 'En Riesgo'
    if 365 < dias <= 730:
        return 'Dormido'
    if dias > 730:
        return 'Perdido'
    # Fallback razonable (gente con 1-2 visitas hace 90-365 días).
    return 'En Riesgo' if visitas >= 1 else 'Perdido'


def _classify_eje_estilo(f: dict) -> str:
    pct_masajes = f['pct_masajes']
    pct_tinas = f['pct_tinas']
    pct_cabanas = f['pct_cabanas']
    pct_bundle = f['pct_reservas_bundle']

    if pct_masajes >= 60:
        return 'Devoto del Masaje'
    if pct_tinas >= 60 and pct_masajes < 30:
        return 'Amante de las Tinas'
    if pct_bundle >= 50:
        return 'Experiencia Completa'
    if pct_cabanas >= 40:
        return 'Buscador de Alojamiento'
    return 'Probador Esporádico'


def _classify_eje_contexto(f: dict) -> str:
    avg = f['avg_cantidad_personas']
    pct_finde = f['pct_finde']
    pct_semana = f['pct_semana']
    pct_verano = f['pct_verano']
    pct_otono = f['pct_otono']
    pct_invierno = f['pct_invierno']
    pct_primavera = f['pct_primavera']
    meses_rel = f['meses_relacion_actual']

    # 'Sin clasificar' por defecto si no hay señal (cliente sin sistema actual).
    if f['total_visitas'] == 0 or avg is None:
        return 'Sin clasificar'

    if 1.8 <= avg <= 2.2 and pct_finde >= 50:
        return 'Pareja Romántica'
    if avg <= 1.3 and pct_semana >= 40:
        return 'Auto-cuidado Solo'
    if avg >= 2.7:
        return 'Grupo'
    if 2.3 <= avg <= 2.7:
        return 'Familiar'
    # Turista Estacional: alguna temporada concentra ≥70%.
    max_temp = max(pct_verano, pct_otono, pct_invierno, pct_primavera)
    if max_temp >= 70:
        return 'Turista Estacional'
    # Local Frecuente: ninguna temporada >50% AND meses_relacion ≥ 12.
    if max_temp <= 50 and meses_rel >= 12:
        return 'Local Frecuente'
    return 'Sin clasificar'


# ---------------------------------------------------------------------------
# CSV header (orden fijo)
# ---------------------------------------------------------------------------
CSV_COLUMNS = [
    'cliente_id', 'tiene_email', 'tiene_telefono',
    # Sistema actual core
    'total_visitas', 'gasto_total', 'ticket_promedio',
    'primera_visita_actual', 'ultima_visita',
    'dias_desde_ultima_visita', 'dias_entre_visitas_avg', 'meses_relacion_actual',
    # Mix servicios
    'count_tinas', 'count_masajes', 'count_cabanas', 'count_otros',
    'pct_tinas', 'pct_masajes', 'pct_cabanas', 'pct_otros',
    'gasto_tinas', 'gasto_masajes', 'gasto_cabanas', 'gasto_otros',
    'servicios_distintos', 'proveedores_distintos',
    # Combos
    'count_reservas_solo_tinas', 'count_reservas_solo_masajes',
    'count_reservas_solo_cabanas', 'count_reservas_bundle',
    'pct_reservas_bundle',
    # Compañía
    'avg_cantidad_personas', 'pct_reservas_solo',
    'pct_reservas_pareja', 'pct_reservas_grupo',
    # Temporal
    'pct_finde', 'pct_semana',
    'pct_verano', 'pct_otono', 'pct_invierno', 'pct_primavera',
    # Pre-sistema
    'tiene_historial_pre_sistema', 'visitas_history_count',
    'primera_visita_history', 'primera_visita_global', 'antiguedad_meses',
    # Etiquetas
    'eje_valor', 'eje_estilo', 'eje_contexto',
]


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Análisis exploratorio one-shot de taxonomía multidimensional de clientes "
        "(Valor + Estilo + Contexto). Genera taxonomy_data.csv + taxonomy_report.md."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--months', type=int, default=24,
            help='Meses hacia atrás del sistema actual (default 24, max 36).',
        )
        parser.add_argument(
            '--output-dir', type=str, default='/tmp/aremko_taxonomy/',
            help='Directorio donde escribir los outputs (se crea si no existe).',
        )

    # ----- Entrada principal -----
    def handle(self, *args, **opts):
        months = int(opts['months'])
        if months < 1 or months > 36:
            raise CommandError('--months debe estar entre 1 y 36')

        output_dir = opts['output_dir']
        os.makedirs(output_dir, exist_ok=True)

        today = timezone.now().date()
        # Primer día del mes "hace N-1 meses".
        total_meses_atras = (today.year * 12 + (today.month - 1)) - (months - 1)
        first_y = total_meses_atras // 12
        first_m = (total_meses_atras % 12) + 1
        periodo_start = date(first_y, first_m, 1)
        periodo_stop = today

        self.stdout.write(self.style.NOTICE(
            f"Período sistema actual: {periodo_start} → {periodo_stop} ({months} meses)"
        ))

        # ----- 1) Recolectar features por cliente -----
        link_method = self._detect_link_method()
        self.stdout.write(f"Método de vinculación Cliente↔ServiceHistory: {link_method}")

        features_by_cliente, meta = self._build_features(
            periodo_start=periodo_start,
            periodo_stop=periodo_stop,
            today=today,
        )

        # ----- 2) Clasificar cada cliente en los 3 ejes -----
        for cid, f in features_by_cliente.items():
            f['eje_valor'] = _classify_eje_valor(f)
            f['eje_estilo'] = _classify_eje_estilo(f)
            f['eje_contexto'] = _classify_eje_contexto(f)

        # ----- 3) Escribir CSV -----
        csv_path = os.path.join(output_dir, 'taxonomy_data.csv')
        self._write_csv(csv_path, features_by_cliente)
        self.stdout.write(self.style.SUCCESS(
            f"CSV escrito: {csv_path} ({len(features_by_cliente)} clientes)"
        ))

        # ----- 4) Escribir reporte MD -----
        md_path = os.path.join(output_dir, 'taxonomy_report.md')
        self._write_report(
            md_path=md_path,
            features=features_by_cliente,
            meta=meta,
            months=months,
            periodo_start=periodo_start,
            periodo_stop=periodo_stop,
            link_method=link_method,
        )
        self.stdout.write(self.style.SUCCESS(f"Reporte escrito: {md_path}"))

    # ----- Detectar método de vinculación -----
    def _detect_link_method(self) -> str:
        """ServiceHistory.cliente es FK directo en este proyecto. Verificar."""
        try:
            ServiceHistory._meta.get_field('cliente')
            return 'FK directo (service_history.cliente_id)'
        except Exception:
            return 'desconocido — revisar manualmente'

    # ----- Construir features por cliente -----
    def _build_features(
        self,
        *,
        periodo_start: date,
        periodo_stop: date,
        today: date,
    ) -> Tuple[Dict[int, dict], dict]:
        """Devuelve (features_by_cliente_id, metadata_de_cobertura)."""

        # --- 1) Clientes con ≥1 VentaReserva no cancelada en el período ---
        ventas_qs = VentaReserva.objects.filter(
            fecha_creacion__date__gte=periodo_start,
            fecha_creacion__date__lte=periodo_stop,
        ).exclude(estado_pago='cancelado').values(
            'id', 'cliente_id', 'fecha_creacion'
        )
        ventas_periodo = list(ventas_qs)
        cliente_ids_sistema = {v['cliente_id'] for v in ventas_periodo if v['cliente_id']}

        # --- 2) Clientes con ≥1 ServiceHistory ---
        sh_agg = ServiceHistory.objects.values('cliente_id').annotate(
            count=Count('id'),
            primera=Min('service_date'),
            ultima=Max('service_date'),
        )
        sh_by_cliente: Dict[int, dict] = {
            row['cliente_id']: {
                'count': row['count'],
                'primera': row['primera'],
                'ultima': row['ultima'],
            }
            for row in sh_agg if row['cliente_id']
        }
        cliente_ids_history = set(sh_by_cliente.keys())

        cliente_ids_ambos = cliente_ids_sistema & cliente_ids_history
        cliente_ids_solo_history = cliente_ids_history - cliente_ids_sistema
        eligibles = cliente_ids_sistema | cliente_ids_history

        self.stdout.write(
            f"  • Sistema actual: {len(cliente_ids_sistema)} clientes"
            f"   • ServiceHistory: {len(cliente_ids_history)}"
            f"   • Ambos: {len(cliente_ids_ambos)}"
        )

        # --- 3) Cliente fields necesarios (solo eligibles) ---
        total_clientes_bd = Cliente.objects.count()
        clientes_info = {
            c['id']: c for c in Cliente.objects.filter(id__in=eligibles).values(
                'id', 'email', 'telefono'
            )
        }

        # --- 4) Todos los ReservaServicio del período (una sola query) ---
        rs_qs = ReservaServicio.objects.filter(
            venta_reserva__fecha_creacion__date__gte=periodo_start,
            venta_reserva__fecha_creacion__date__lte=periodo_stop,
        ).exclude(
            venta_reserva__estado_pago='cancelado',
        ).values(
            'venta_reserva_id',
            'venta_reserva__cliente_id',
            'venta_reserva__fecha_creacion',
            'fecha_agendamiento',
            'servicio_id',
            'servicio__tipo_servicio',
            'precio_unitario_venta',
            'servicio__precio_base',
            'cantidad_personas',
            'proveedor_asignado_id',
        )

        # Agregadores por cliente.
        # Estructuras: por cliente_id, acumulamos.
        per_cli: Dict[int, dict] = defaultdict(lambda: {
            'fechas_creacion_ventas': set(),      # set de fecha_creacion.date()
            'venta_ids': set(),                    # set de venta_reserva_id
            'count_familia': Counter(),            # familia → cantidad de RS
            'gasto_familia': defaultdict(float),   # familia → revenue
            'servicios_distintos': set(),
            'proveedores_distintos': set(),
            'cantidad_personas_lista': [],         # lista de cantidad_personas
            'fechas_agendamiento': [],             # lista de fecha_agendamiento (date)
            'venta_familias': defaultdict(set),    # venta_id → set de familias core
        })

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
            cant = row['cantidad_personas'] or 1
            rev = float(precio_unit) * cant
            agg['gasto_familia'][fam] += rev

            agg['servicios_distintos'].add(row['servicio_id'])
            if row['proveedor_asignado_id']:
                agg['proveedores_distintos'].add(row['proveedor_asignado_id'])
            agg['cantidad_personas_lista'].append(cant)

            fa = row['fecha_agendamiento']
            if fa is not None:
                agg['fechas_agendamiento'].append(fa)

            if fam in FAMILIAS_CORE:
                agg['venta_familias'][vid].add(fam)
            else:
                # Marcamos la venta como existente aunque solo tenga 'otros'.
                agg['venta_familias'].setdefault(vid, set())

        # --- 5) Construir el dict final por cliente ---
        features: Dict[int, dict] = {}
        for cid in eligibles:
            info = clientes_info.get(cid, {})
            agg = per_cli.get(cid, None)

            # Datos del sistema actual
            if agg:
                visitas = len(agg['venta_ids'])
                count_tinas = agg['count_familia'].get('tinas', 0)
                count_masajes = agg['count_familia'].get('masajes', 0)
                count_cabanas = agg['count_familia'].get('cabanas', 0)
                count_otros = agg['count_familia'].get('otros', 0)
                total_servicios = count_tinas + count_masajes + count_cabanas + count_otros

                gasto_tinas = round(agg['gasto_familia'].get('tinas', 0.0), 2)
                gasto_masajes = round(agg['gasto_familia'].get('masajes', 0.0), 2)
                gasto_cabanas = round(agg['gasto_familia'].get('cabanas', 0.0), 2)
                gasto_otros = round(agg['gasto_familia'].get('otros', 0.0), 2)
                gasto_total = round(gasto_tinas + gasto_masajes + gasto_cabanas + gasto_otros, 2)

                ticket_promedio = round(gasto_total / visitas, 2) if visitas else 0.0

                fechas_visitas = sorted(agg['fechas_creacion_ventas'])
                primera_visita_actual = fechas_visitas[0] if fechas_visitas else None
                ultima_visita = fechas_visitas[-1] if fechas_visitas else None
                dias_desde_ultima = (today - ultima_visita).days if ultima_visita else None
                if primera_visita_actual and ultima_visita and len(fechas_visitas) >= 2:
                    span_dias = (ultima_visita - primera_visita_actual).days
                    dias_entre_avg = round(span_dias / (len(fechas_visitas) - 1), 1)
                    meses_rel = round(span_dias / 30, 1)
                else:
                    dias_entre_avg = None
                    meses_rel = 0.0

                # Mix porcentual
                if total_servicios:
                    pct_tinas = round(count_tinas / total_servicios * 100, 1)
                    pct_masajes = round(count_masajes / total_servicios * 100, 1)
                    pct_cabanas = round(count_cabanas / total_servicios * 100, 1)
                    pct_otros = round(count_otros / total_servicios * 100, 1)
                else:
                    pct_tinas = pct_masajes = pct_cabanas = pct_otros = 0.0

                # Combos por venta
                solo_t = solo_m = solo_c = bundle = 0
                for vid, fams in agg['venta_familias'].items():
                    if fams == {'tinas'}:
                        solo_t += 1
                    elif fams == {'masajes'}:
                        solo_m += 1
                    elif fams == {'cabanas'}:
                        solo_c += 1
                    elif len(fams) >= 2:
                        bundle += 1
                pct_bundle = round(bundle / visitas * 100, 1) if visitas else 0.0

                # Compañía
                cant_list = agg['cantidad_personas_lista']
                if cant_list:
                    avg_cant = round(sum(cant_list) / len(cant_list), 2)
                    total_c = len(cant_list)
                    pct_solo = round(sum(1 for c in cant_list if c == 1) / total_c * 100, 1)
                    pct_pareja = round(sum(1 for c in cant_list if c == 2) / total_c * 100, 1)
                    pct_grupo = round(sum(1 for c in cant_list if c >= 3) / total_c * 100, 1)
                else:
                    avg_cant = None
                    pct_solo = pct_pareja = pct_grupo = 0.0

                # Temporal
                fa_list = agg['fechas_agendamiento']
                if fa_list:
                    n_fa = len(fa_list)
                    finde = sum(1 for d in fa_list if d.weekday() >= 5)
                    pct_finde = round(finde / n_fa * 100, 1)
                    pct_semana = round((n_fa - finde) / n_fa * 100, 1)
                    season_counts = Counter(_season_for_month(d.month) for d in fa_list)
                    pct_verano = round(season_counts.get('verano', 0) / n_fa * 100, 1)
                    pct_otono = round(season_counts.get('otono', 0) / n_fa * 100, 1)
                    pct_invierno = round(season_counts.get('invierno', 0) / n_fa * 100, 1)
                    pct_primavera = round(season_counts.get('primavera', 0) / n_fa * 100, 1)
                else:
                    pct_finde = pct_semana = 0.0
                    pct_verano = pct_otono = pct_invierno = pct_primavera = 0.0

                servicios_distintos = len(agg['servicios_distintos'])
                proveedores_distintos = len(agg['proveedores_distintos'])
            else:
                # Cliente solo en ServiceHistory
                visitas = 0
                count_tinas = count_masajes = count_cabanas = count_otros = 0
                gasto_tinas = gasto_masajes = gasto_cabanas = gasto_otros = 0.0
                gasto_total = 0.0
                ticket_promedio = 0.0
                primera_visita_actual = None
                ultima_visita = None
                dias_desde_ultima = None
                dias_entre_avg = None
                meses_rel = 0.0
                pct_tinas = pct_masajes = pct_cabanas = pct_otros = 0.0
                solo_t = solo_m = solo_c = bundle = 0
                pct_bundle = 0.0
                avg_cant = None
                pct_solo = pct_pareja = pct_grupo = 0.0
                pct_finde = pct_semana = 0.0
                pct_verano = pct_otono = pct_invierno = pct_primavera = 0.0
                servicios_distintos = proveedores_distintos = 0

            # Pre-sistema
            sh = sh_by_cliente.get(cid)
            if sh:
                tiene_hist = True
                visitas_hist = sh['count']
                primera_hist = sh['primera']
            else:
                tiene_hist = False
                visitas_hist = 0
                primera_hist = None

            # primera_visita_global = min(primera_visita_actual, primera_hist)
            candidatos_globales = [d for d in (primera_visita_actual, primera_hist) if d is not None]
            primera_global = min(candidatos_globales) if candidatos_globales else None
            antiguedad_meses = (
                round((today - primera_global).days / 30) if primera_global else 0
            )

            features[cid] = {
                'cliente_id': cid,
                'tiene_email': bool(info.get('email')),
                'tiene_telefono': bool(info.get('telefono')),
                'total_visitas': visitas,
                'gasto_total': gasto_total,
                'ticket_promedio': ticket_promedio,
                'primera_visita_actual': primera_visita_actual.isoformat() if primera_visita_actual else '',
                'ultima_visita': ultima_visita.isoformat() if ultima_visita else '',
                'dias_desde_ultima_visita': dias_desde_ultima if dias_desde_ultima is not None else '',
                'dias_entre_visitas_avg': dias_entre_avg if dias_entre_avg is not None else '',
                'meses_relacion_actual': meses_rel,
                'count_tinas': count_tinas,
                'count_masajes': count_masajes,
                'count_cabanas': count_cabanas,
                'count_otros': count_otros,
                'pct_tinas': pct_tinas, 'pct_masajes': pct_masajes,
                'pct_cabanas': pct_cabanas, 'pct_otros': pct_otros,
                'gasto_tinas': gasto_tinas, 'gasto_masajes': gasto_masajes,
                'gasto_cabanas': gasto_cabanas, 'gasto_otros': gasto_otros,
                'servicios_distintos': servicios_distintos,
                'proveedores_distintos': proveedores_distintos,
                'count_reservas_solo_tinas': solo_t,
                'count_reservas_solo_masajes': solo_m,
                'count_reservas_solo_cabanas': solo_c,
                'count_reservas_bundle': bundle,
                'pct_reservas_bundle': pct_bundle,
                'avg_cantidad_personas': avg_cant if avg_cant is not None else '',
                'pct_reservas_solo': pct_solo,
                'pct_reservas_pareja': pct_pareja,
                'pct_reservas_grupo': pct_grupo,
                'pct_finde': pct_finde, 'pct_semana': pct_semana,
                'pct_verano': pct_verano, 'pct_otono': pct_otono,
                'pct_invierno': pct_invierno, 'pct_primavera': pct_primavera,
                'tiene_historial_pre_sistema': tiene_hist,
                'visitas_history_count': visitas_hist,
                'primera_visita_history': primera_hist.isoformat() if primera_hist else '',
                'primera_visita_global': primera_global.isoformat() if primera_global else '',
                'antiguedad_meses': antiguedad_meses,
            }

        meta = {
            'total_clientes_bd': total_clientes_bd,
            'cliente_ids_sistema': cliente_ids_sistema,
            'cliente_ids_history': cliente_ids_history,
            'cliente_ids_ambos': cliente_ids_ambos,
            'cliente_ids_solo_history': cliente_ids_solo_history,
        }
        return features, meta

    # ----- Escribir CSV -----
    def _write_csv(self, csv_path: str, features: Dict[int, dict]):
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for cid in sorted(features.keys()):
                row = features[cid]
                # Asegurar que todas las columnas estén presentes.
                row_out = {col: row.get(col, '') for col in CSV_COLUMNS}
                writer.writerow(row_out)

    # ----- Escribir reporte Markdown -----
    def _write_report(
        self,
        *,
        md_path: str,
        features: Dict[int, dict],
        meta: dict,
        months: int,
        periodo_start: date,
        periodo_stop: date,
        link_method: str,
    ):
        total = len(features)
        lines: List[str] = []
        ap = lines.append

        ap(f"# Reporte exploratorio — Taxonomía de Clientes Aremko")
        ap("")
        ap(f"Generado: {timezone.now().isoformat(timespec='seconds')}")
        ap(f"Período sistema actual: **{periodo_start} → {periodo_stop}** ({months} meses)")
        ap("")

        # ----- Cobertura -----
        n_sistema = len(meta['cliente_ids_sistema'])
        n_history = len(meta['cliente_ids_history'])
        n_ambos = len(meta['cliente_ids_ambos'])
        n_solo_history = len(meta['cliente_ids_solo_history'])
        pct_ambos_vs_history = (n_ambos / n_history * 100) if n_history else 0
        ap("## Cobertura de Historial Pre-Sistema")
        ap("")
        ap(f"- Total Cliente en BD: **{meta['total_clientes_bd']:,}**")
        ap(f"- Cliente con ≥1 reserva en últimos {months} meses (sistema actual): **{n_sistema:,}**")
        ap(f"- Cliente con ≥1 registro en ServiceHistory: **{n_history:,}**")
        ap(f"- Cliente con AMBOS (linkeados): **{n_ambos:,}** ({pct_ambos_vs_history:.1f}% de los con historial)")
        ap(f"- Cliente solo en ServiceHistory (no volvieron al sistema actual): **{n_solo_history:,}**")
        ap(f"- Método de vinculación usado: {link_method}")
        ap("")
        ap(f"**Total de filas en taxonomy_data.csv: {total:,}** "
           f"(unión sistema actual ∪ ServiceHistory)")
        ap("")

        # ----- Distribuciones por eje -----
        valor_counter = Counter(f['eje_valor'] for f in features.values())
        estilo_counter = Counter(f['eje_estilo'] for f in features.values())
        contexto_counter = Counter(f['eje_contexto'] for f in features.values())

        def _seccion_distribucion(title: str, counter: Counter, orden: List[str]):
            ap(f"## {title}")
            ap("")
            ap("| Categoría | Clientes | % |")
            ap("|---|---:|---:|")
            for k in orden:
                n = counter.get(k, 0)
                pct = (n / total * 100) if total else 0
                ap(f"| {k} | {n:,} | {pct:.1f}% |")
            # cualquier categoría inesperada
            otras = set(counter.keys()) - set(orden)
            for k in sorted(otras):
                n = counter[k]
                pct = (n / total * 100) if total else 0
                ap(f"| _{k}_ | {n:,} | {pct:.1f}% |")
            ap("")

        _seccion_distribucion('Eje Valor', valor_counter, EJE_VALOR_ORDEN)
        _seccion_distribucion('Eje Estilo', estilo_counter, EJE_ESTILO_ORDEN)
        _seccion_distribucion('Eje Contexto', contexto_counter, EJE_CONTEXTO_ORDEN)

        # ----- Matriz Valor × Estilo -----
        ap("## Matriz cruzada: Valor × Estilo")
        ap("")
        matriz_vs = Counter()
        for f in features.values():
            matriz_vs[(f['eje_valor'], f['eje_estilo'])] += 1
        # Tabla
        ap("| Valor \\ Estilo | " + " | ".join(EJE_ESTILO_ORDEN) + " |")
        ap("|---|" + "---:|" * len(EJE_ESTILO_ORDEN))
        for v in EJE_VALOR_ORDEN:
            row_vals = [str(matriz_vs.get((v, e), 0)) for e in EJE_ESTILO_ORDEN]
            ap(f"| {v} | " + " | ".join(row_vals) + " |")
        ap("")

        # ----- Matriz Estilo × Contexto -----
        ap("## Matriz cruzada: Estilo × Contexto")
        ap("")
        matriz_ec = Counter()
        for f in features.values():
            matriz_ec[(f['eje_estilo'], f['eje_contexto'])] += 1
        ap("| Estilo \\ Contexto | " + " | ".join(EJE_CONTEXTO_ORDEN) + " |")
        ap("|---|" + "---:|" * len(EJE_CONTEXTO_ORDEN))
        for e in EJE_ESTILO_ORDEN:
            row_vals = [str(matriz_ec.get((e, c), 0)) for c in EJE_CONTEXTO_ORDEN]
            ap(f"| {e} | " + " | ".join(row_vals) + " |")
        ap("")

        # ----- Top 5 por combinación de interés -----
        ap("## Top 5 clientes por combinación de interés (por gasto_total)")
        ap("")
        ap("> Se muestran solo combinaciones con al menos 1 cliente. ID interno (sin PII).")
        ap("")
        for (valor_label, estilo_label) in TOP_COMBOS_INTERES:
            subset = [
                f for f in features.values()
                if f['eje_valor'] == valor_label and f['eje_estilo'] == estilo_label
            ]
            if not subset:
                ap(f"### {valor_label} × {estilo_label}: _sin clientes en esta combinación_")
                ap("")
                continue
            subset.sort(key=lambda f: f['gasto_total'], reverse=True)
            top5 = subset[:5]
            ap(f"### {valor_label} × {estilo_label} (n={len(subset):,})")
            ap("")
            ap("| cliente_id | gasto_total | visitas | antigüedad (meses) |")
            ap("|---:|---:|---:|---:|")
            for f in top5:
                ap(
                    f"| {f['cliente_id']} | ${int(f['gasto_total']):,} | "
                    f"{f['total_visitas']} | {f['antiguedad_meses']} |"
                )
            ap("")

        # ----- Estadísticas descriptivas -----
        ap("## Estadísticas descriptivas por dimensión")
        ap("")

        def _stats_dim(label: str, values: List[float]):
            if not values:
                ap(f"- **{label}**: sin datos")
                return
            vs = sorted(values)
            n = len(vs)
            mean = statistics.mean(vs)
            median = statistics.median(vs)
            p25 = vs[n // 4]
            p75 = vs[(3 * n) // 4] if n >= 4 else vs[-1]
            mx = vs[-1]
            ap(f"- **{label}** (n={n:,}): "
               f"media={mean:,.0f}, mediana={median:,.0f}, "
               f"p25={p25:,.0f}, p75={p75:,.0f}, max={mx:,.0f}")

        gastos = [f['gasto_total'] for f in features.values() if f['gasto_total'] > 0]
        tickets = [f['ticket_promedio'] for f in features.values() if f['ticket_promedio'] > 0]
        visitas_list = [f['total_visitas'] for f in features.values() if f['total_visitas'] > 0]
        dias_entre = [f['dias_entre_visitas_avg'] for f in features.values()
                      if isinstance(f['dias_entre_visitas_avg'], (int, float))]
        antiguedades = [f['antiguedad_meses'] for f in features.values() if f['antiguedad_meses'] > 0]

        _stats_dim('gasto_total (CLP, solo > 0)', gastos)
        _stats_dim('ticket_promedio (CLP)', tickets)
        _stats_dim('total_visitas', visitas_list)
        _stats_dim('dias_entre_visitas_avg', dias_entre)
        _stats_dim('antiguedad_meses', antiguedades)
        ap("")

        # ----- % con historial pre-sistema por eje Valor -----
        ap("### % de clientes con historial pre-sistema por Eje Valor")
        ap("")
        ap("| Eje Valor | n total | con historial | % con historial |")
        ap("|---|---:|---:|---:|")
        for v in EJE_VALOR_ORDEN:
            subset = [f for f in features.values() if f['eje_valor'] == v]
            n = len(subset)
            con_h = sum(1 for f in subset if f['tiene_historial_pre_sistema'])
            pct = (con_h / n * 100) if n else 0
            ap(f"| {v} | {n:,} | {con_h:,} | {pct:.1f}% |")
        ap("")

        # ----- Alertas automáticas -----
        ap("## Alertas automáticas")
        ap("")
        alertas: List[str] = []

        def _check_distrib(counter: Counter, eje: str):
            for cat, n in counter.items():
                pct = (n / total * 100) if total else 0
                if pct > 50:
                    alertas.append(
                        f"⚠️ **{eje} → {cat}** representa {pct:.1f}% (>50%): "
                        f"categoría muy gruesa, considerar subdividir."
                    )
                if 0 < pct < 1:
                    alertas.append(
                        f"⚠️ **{eje} → {cat}** representa {pct:.2f}% (<1%): "
                        f"categoría muy fina, considerar fusionar."
                    )

        _check_distrib(valor_counter, 'Eje Valor')
        _check_distrib(estilo_counter, 'Eje Estilo')
        _check_distrib(contexto_counter, 'Eje Contexto')

        # Celdas vacías en Valor × Estilo
        for v in EJE_VALOR_ORDEN:
            for e in EJE_ESTILO_ORDEN:
                if matriz_vs.get((v, e), 0) == 0:
                    alertas.append(
                        f"⚠️ Combinación **{v} × {e}** vacía: revisar definición."
                    )

        if alertas:
            for a in alertas:
                ap(f"- {a}")
        else:
            ap("_Sin alertas._")
        ap("")

        # ----- Footer -----
        ap("---")
        ap(f"_Fin del reporte. CSV adjunto: `taxonomy_data.csv` "
           f"({total:,} filas, {len(CSV_COLUMNS)} columnas, sin PII)._")

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines) + "\n")
