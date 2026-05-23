"""
analizar_bandeja_potencial
==========================

Comando read-only de diagnóstico para Operación Vuelta a Casa.

Analiza CUÁNTOS clientes calificarían para cada prioridad de la bandeja
sin generar ni un solo ContactoWhatsApp. Útil para:
  - Validar el "cold start" antes de correr el comando real
  - Detectar plantillas faltantes (clientes "sin script aplicable")
  - Estimar cuántos días dura la cola de cada prioridad
  - Decidir si vale la pena aplicar cap por prioridad

Uso:
    python manage.py analizar_bandeja_potencial

NO escribe a BD. NO altera estado. Solo SELECT + cálculos en memoria + print.

Pre-carga los 14 scripts a memoria y hace la cascada inline (sin queries
adicionales) → procesa ~14K clientes en <30s.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from ventas.models import ClienteTaxonomia, ContactoWhatsApp, ScriptWhatsApp
from ventas.services.bandeja_whatsapp_service import calcular_prioridad


DIAS_ANTI_SAT = 30

PRIORIDAD_LABEL = {
    0: 'P0 · Mesa chica (Leal/Campeón)        ',
    1: 'P1 · En Riesgo óptimo (95-105d)       ',
    2: 'P2 · En Prueba ventana (30/60/80d)    ',
    3: 'P3 · Dormido óptimo (195-210d)        ',
    4: 'P4 · Regular atrasado                 ',
    5: 'P5 · En Riesgo (resto)                ',
    6: 'P6 · Dormido (resto)                  ',
}


def _buscar_inline(scripts, estado, estilo, contexto, salva):
    """Replica buscar_script_cascada pero sobre lista en memoria (sin queries)."""
    base = [s for s in scripts if s['estado_valor_target'] == estado and s['salva'] == salva]
    # Nivel 1: exacto
    for s in base:
        if s['cohorte_estilo'] == estilo and s['cohorte_contexto'] == contexto:
            return s
    # Nivel 2: estilo + cualquier contexto
    for s in base:
        if s['cohorte_estilo'] == estilo and s['cohorte_contexto'] == '':
            return s
    # Nivel 3: cualquier estilo + contexto
    for s in base:
        if s['cohorte_estilo'] == '' and s['cohorte_contexto'] == contexto:
            return s
    # Nivel 4: genérico
    for s in base:
        if s['cohorte_estilo'] == '' and s['cohorte_contexto'] == '':
            return s
    return None


class Command(BaseCommand):
    help = (
        "Analiza la bandeja potencial sin generar contactos. "
        "Read-only — útil para diagnóstico de cold start, cobertura de plantillas, "
        "y decisiones de cap por prioridad."
    )

    def handle(self, *args, **opts):
        hoy = timezone.now().date()

        # ---- Precargar scripts en memoria ----
        scripts = list(
            ScriptWhatsApp.objects.filter(activo=True).values(
                'script_id', 'estado_valor_target',
                'cohorte_estilo', 'cohorte_contexto', 'salva',
            )
        )

        # ---- Precargar salvas previas por cliente (1 query agregada) ----
        salvas_por_cliente = dict(
            ContactoWhatsApp.objects.filter(estado='enviado')
            .values('cliente_id')
            .annotate(c=Count('id'))
            .values_list('cliente_id', 'c')
        )

        # ---- Cargar candidatos elegibles ----
        qs = (
            ClienteTaxonomia.objects
            .select_related('cliente')
            .exclude(cliente__opt_out_whatsapp=True)
            .exclude(cliente__telefono__isnull=True)
            .exclude(cliente__telefono='')
            .exclude(cliente__proximo_contacto_no_antes_de__gt=hoy)
            .exclude(cliente__ultimo_contacto_outbound__gte=hoy - timedelta(days=DIAS_ANTI_SAT))
        )
        elegibles = list(qs)
        total_tax = ClienteTaxonomia.objects.count()

        # ---- Iterar y clasificar ----
        por_prio: Counter = Counter()
        sin_prio = 0
        sin_script_por_prio: Counter = Counter()
        salvas_p0: Counter = Counter()
        # Bonus: distribución cohorte × prioridad para detectar gaps de plantillas
        sin_script_detalle: Counter = Counter()

        for tax in elegibles:
            p = calcular_prioridad(
                eje_valor=tax.eje_valor,
                dias_desde_ultima_visita=tax.dias_desde_ultima_visita,
                primera_visita_actual=tax.primera_visita_actual,
                dias_entre_visitas_avg=tax.dias_entre_visitas_avg,
                ultimo_contacto_outbound=tax.cliente.ultimo_contacto_outbound,
                hoy=hoy,
            )
            if p is None:
                sin_prio += 1
                continue
            por_prio[p] += 1

            salva = salvas_por_cliente.get(tax.cliente_id, 0) + 1
            if p == 0:
                salvas_p0[salva] += 1

            script = _buscar_inline(
                scripts, tax.eje_valor, tax.eje_estilo, tax.eje_contexto, salva
            )
            if script is None:
                sin_script_por_prio[p] += 1
                sin_script_detalle[
                    (tax.eje_valor, tax.eje_estilo, tax.eje_contexto, salva)
                ] += 1

        # ============================================================
        # Reporte
        # ============================================================
        out = self.stdout
        out.write('')
        out.write('=' * 70)
        out.write(f'ANÁLISIS BANDEJA POTENCIAL · {hoy}')
        out.write('=' * 70)
        out.write('')

        out.write('Universo:')
        out.write(f'  ClienteTaxonomia total:           {total_tax:>6}')
        out.write(f'  Elegibles tras filtros:           {len(elegibles):>6}')
        excl = total_tax - len(elegibles)
        pct = (excl / total_tax * 100) if total_tax else 0
        out.write(f'  Excluidos por filtros:            {excl:>6}  ({pct:.1f}%)')
        out.write('')

        out.write('Desglose por prioridad:')
        out.write('  ' + '-' * 64)
        total_priorizados = 0
        total_sin_script = 0
        for p in sorted(por_prio.keys()):
            label = PRIORIDAD_LABEL.get(p, f'P{p}                                   ')
            sin_s = sin_script_por_prio.get(p, 0)
            total_priorizados += por_prio[p]
            total_sin_script += sin_s
            out.write(
                f'  [{por_prio[p]:>5}]  {label}│ sin script: {sin_s:>4}'
            )
        out.write(
            f'  [{sin_prio:>5}]  '
            f'Sin prioridad (no entran a bandeja)    │'
        )
        out.write('  ' + '-' * 64)
        out.write(
            f'  Total priorizados: {total_priorizados}  ·  '
            f'Total sin script: {total_sin_script}'
        )
        check = total_priorizados + sin_prio
        marker = '✓' if check == len(elegibles) else '✗ INCONSISTENCIA'
        out.write(f'  Verificación suma: {check} (debe = {len(elegibles)})  {marker}')
        out.write('')

        out.write('Distribución de salvas en P0 (Leal/Campeón):')
        if salvas_p0:
            for s in sorted(salvas_p0.keys()):
                out.write(f'  Salva {s}: {salvas_p0[s]:>5} clientes')
        else:
            out.write('  (P0 vacía en este análisis)')
        out.write('')

        # ---- Detalle de cohortes sin script (para detectar plantillas faltantes) ----
        if sin_script_detalle:
            out.write('Top 10 cohortes sin script aplicable:')
            out.write('  ' + '-' * 64)
            top = sin_script_detalle.most_common(10)
            for (valor, estilo, contexto, salva), n in top:
                out.write(
                    f'  [{n:>4}] valor={valor!r}, estilo={estilo!r}, '
                    f'contexto={contexto!r}, salva={salva}'
                )
            out.write('')

        out.write('=' * 70)
