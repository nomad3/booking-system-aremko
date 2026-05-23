"""
generar_bandeja_whatsapp_diaria
================================

Cron diario (06:00 AM Santiago) — Operación Vuelta a Casa, Etapa 3.

Selecciona ~50 clientes elegibles para WhatsApp manual, los prioriza según
ciclo de vida, escoge la plantilla apropiada por cohorte y deja todo listo
en `ContactoWhatsApp` para que el operador procese la bandeja durante el día.

Uso:
    # Producción (cron diario):
    python manage.py generar_bandeja_whatsapp_diaria

    # Ver la bandeja del día sin escribir a DB:
    python manage.py generar_bandeja_whatsapp_diaria --dry-run

    # Probar con un cliente específico:
    python manage.py generar_bandeja_whatsapp_diaria --dry-run --cliente-id 7821

    # Limitar a N candidatos (debug):
    python manage.py generar_bandeja_whatsapp_diaria --dry-run --limit 5

    # Re-generar para una fecha específica (testing):
    python manage.py generar_bandeja_whatsapp_diaria --fecha 2026-06-10 --dry-run

Algoritmo:
    1. Idempotencia: si ya hay ContactoWhatsApp con fecha_sugerido=hoy,
       abortar (a menos que --force).
    2. Cargar ClienteTaxonomia.select_related('cliente') excluyendo:
         - opt_out_whatsapp = True
         - sin teléfono
         - proximo_contacto_no_antes_de > hoy
         - ultimo_contacto_outbound dentro de los últimos 30 días
    3. Calcular prioridad por cliente (0-6, ver calcular_prioridad).
       Descartar None (no califica).
    4. Ordenar por (prioridad ASC, gasto_total DESC).
    5. Tomar primeros --limit (default 50).
    6. Para cada candidato:
       a. Calcular salva = count(ContactoWhatsApp enviados al cliente) + 1
       b. Saltar si salva > 3 (ya agotó las 3 salvas históricas)
       c. Buscar script en cascada de 5 niveles
       d. Si no hay script → loguear warning, saltar
       e. Renderizar mensaje con SafeDict (tolerante a placeholders faltantes)
       f. Crear ContactoWhatsApp con snapshot completo
    7. Reportar por consola: cuántos generados, por prioridad, warnings.

Notas:
    - El cron `recalcular_taxonomia_clientes` debe correr ANTES (05:30) para
      que la bandeja use el snapshot más fresco.
    - El cron nocturno `cruzar_reservas_contactos_whatsapp` (Etapa 6) corre
      después para atribuir conversiones.
    - Para Leal/Campeón el matching es por inactividad de contacto, no por
      caída de tramo — ver Prioridad 0 en calcular_prioridad.
"""

from __future__ import annotations

import logging
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import List, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from ventas.models import (
    Cliente,
    ClienteTaxonomia,
    ContactoWhatsApp,
    ScriptWhatsApp,
)
from ventas.services.bandeja_whatsapp_service import (
    buscar_script_cascada,
    build_render_context,
    calcular_prioridad,
)


logger = logging.getLogger(__name__)


# Etiquetas humanas para las prioridades (usadas solo en stdout, no en DB)
PRIORIDAD_LABEL = {
    0: 'P0 · Mesa chica (Leal/Campeón)',
    1: 'P1 · En Riesgo óptimo (95-105d)',
    2: 'P2 · En Prueba momento clave',
    3: 'P3 · Dormido ventana 6-7m',
    4: 'P4 · Regular atrasado',
    5: 'P5 · En Riesgo (resto)',
    6: 'P6 · Dormido (resto)',
}


class Command(BaseCommand):
    help = (
        "Genera la bandeja diaria de WhatsApp (~50 contactos) para el operador. "
        "Diseñado para correr como cron a las 06:00 AM Santiago."
    )

    DEFAULT_LIMIT = 50
    DIAS_ANTI_SATURACION = 30
    MAX_SALVAS = 3

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='No escribe a DB. Solo reporta qué pasaría.',
        )
        parser.add_argument(
            '--limit', type=int, default=self.DEFAULT_LIMIT,
            help=f'Máximo de contactos a generar (default {self.DEFAULT_LIMIT}).',
        )
        parser.add_argument(
            '--cliente-id', type=int, default=None,
            help='Solo procesa este cliente (para debug). Implica --dry-run si no se especifica lo contrario.',
        )
        parser.add_argument(
            '--fecha', type=str, default=None,
            help='Fecha objetivo YYYY-MM-DD (default = hoy). Útil para regenerar testing.',
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Sobreescribe si ya existe bandeja para la fecha (borra pendientes previos).',
        )

    # ========================================================================
    # Entry point
    # ========================================================================

    def handle(self, *args, **opts):
        t0 = time.time()
        dry_run = opts['dry_run']
        limit = opts['limit']
        cliente_id_filter = opts['cliente_id']
        fecha_str = opts['fecha']
        force = opts['force']

        # ---- Resolver fecha objetivo ----
        if fecha_str:
            try:
                fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                raise CommandError(f"--fecha inválido: '{fecha_str}'. Formato esperado: YYYY-MM-DD.")
        else:
            fecha_obj = timezone.now().date()

        self.stdout.write(self.style.NOTICE(
            f"Operación Vuelta a Casa — bandeja para {fecha_obj} "
            f"{'(DRY-RUN)' if dry_run else '(escribiendo a DB)'}"
        ))

        # ---- Chequeo idempotencia ----
        pendientes_existentes = ContactoWhatsApp.objects.filter(
            fecha_sugerido=fecha_obj,
            estado='pendiente',
        ).count()

        if pendientes_existentes > 0 and not force and not cliente_id_filter:
            self.stdout.write(self.style.WARNING(
                f"Ya existen {pendientes_existentes} contactos pendientes para {fecha_obj}. "
                f"Abortando (usa --force para regenerar)."
            ))
            return

        if force and pendientes_existentes > 0 and not dry_run:
            deleted, _ = ContactoWhatsApp.objects.filter(
                fecha_sugerido=fecha_obj, estado='pendiente'
            ).delete()
            self.stdout.write(self.style.WARNING(
                f"  --force: borrados {deleted} pendientes previos para {fecha_obj}"
            ))

        # ---- Cargar candidatos ----
        candidatos = self._cargar_candidatos(fecha_obj, cliente_id_filter)
        self.stdout.write(f"  Candidatos elegibles tras filtros: {len(candidatos)}")

        # ---- Calcular prioridades ----
        candidatos_priorizados = self._asignar_prioridades(candidatos, fecha_obj)
        self.stdout.write(f"  Candidatos con prioridad asignada: {len(candidatos_priorizados)}")

        # ---- Ordenar y limitar ----
        candidatos_priorizados.sort(
            key=lambda x: (x[1], -(x[0].gasto_total or 0))
        )
        if not cliente_id_filter:
            candidatos_priorizados = candidatos_priorizados[:limit]

        # ---- Generar contactos ----
        resultados = self._generar_contactos(
            candidatos_priorizados, fecha_obj, dry_run=dry_run
        )

        # ---- Reporte final ----
        elapsed = time.time() - t0
        self._reportar(resultados, elapsed, dry_run)

    # ========================================================================
    # Carga de candidatos
    # ========================================================================

    def _cargar_candidatos(
        self, fecha_obj: date, cliente_id_filter: Optional[int]
    ) -> List[ClienteTaxonomia]:
        """Devuelve lista de ClienteTaxonomia + cliente prefetched que pasan
        los filtros base (opt-out, sin teléfono, gracia, anti-saturación)."""

        qs = (
            ClienteTaxonomia.objects
            .select_related('cliente')
            .exclude(cliente__opt_out_whatsapp=True)
            .exclude(cliente__telefono__isnull=True)
            .exclude(cliente__telefono='')
            .exclude(cliente__proximo_contacto_no_antes_de__gt=fecha_obj)
        )

        # Anti-saturación: excluir contactados en últimos 30 días
        # (Para Leal/Campeón este filtro es el GATING, no exclusión: P0 requiere
        # ultimo_contacto_outbound NULL o > 30d. Lo dejamos en el exclude porque
        # P0 también lo respeta — es coherente.)
        corte_anti_saturacion = fecha_obj - timedelta(days=self.DIAS_ANTI_SATURACION)
        qs = qs.exclude(cliente__ultimo_contacto_outbound__gte=corte_anti_saturacion)

        if cliente_id_filter:
            qs = qs.filter(cliente_id=cliente_id_filter)

        return list(qs)

    # ========================================================================
    # Asignación de prioridades
    # ========================================================================

    def _asignar_prioridades(
        self, candidatos: List[ClienteTaxonomia], fecha_obj: date
    ) -> List[tuple]:
        """Devuelve [(ClienteTaxonomia, prioridad)] descartando los None."""
        out = []
        for tax in candidatos:
            cliente = tax.cliente
            p = calcular_prioridad(
                eje_valor=tax.eje_valor,
                dias_desde_ultima_visita=tax.dias_desde_ultima_visita,
                primera_visita_actual=tax.primera_visita_actual,
                dias_entre_visitas_avg=tax.dias_entre_visitas_avg,
                ultimo_contacto_outbound=cliente.ultimo_contacto_outbound,
                hoy=fecha_obj,
            )
            if p is not None:
                out.append((tax, p))
        return out

    # ========================================================================
    # Generación de contactos
    # ========================================================================

    def _generar_contactos(
        self, candidatos_priorizados: List[tuple], fecha_obj: date, dry_run: bool
    ) -> dict:
        """Para cada candidato resuelve script + render y crea ContactoWhatsApp.

        Returns:
            dict con keys: 'creados', 'sin_script', 'agotados', 'por_prioridad',
            'sample' (lista de hasta 3 dicts para mostrar en stdout)
        """
        scripts_qs = ScriptWhatsApp.objects.filter(activo=True)
        creados = 0
        sin_script = 0
        agotados = 0
        por_prioridad: Counter = Counter()
        sample: List[dict] = []

        for tax, prioridad in candidatos_priorizados:
            cliente = tax.cliente

            # ---- Cuántas salvas ya recibió este cliente (en la vida) ----
            salvas_previas = ContactoWhatsApp.objects.filter(
                cliente_id=cliente.id, estado='enviado'
            ).count()
            salva = salvas_previas + 1

            if salva > self.MAX_SALVAS:
                agotados += 1
                continue

            # ---- Buscar script en cascada ----
            script = buscar_script_cascada(
                scripts_qs,
                estado_valor=tax.eje_valor,
                estilo=tax.eje_estilo,
                contexto=tax.eje_contexto,
                salva=salva,
            )
            if script is None:
                sin_script += 1
                logger.warning(
                    "Sin script aplicable: cliente_id=%s estado=%r estilo=%r contexto=%r salva=%s",
                    cliente.id, tax.eje_valor, tax.eje_estilo, tax.eje_contexto, salva,
                )
                continue

            # ---- Renderizar mensaje ----
            ctx = build_render_context(cliente, tax, fecha_obj)
            mensaje = script.plantilla_texto.format_map(ctx)

            # ---- Persistir (o simular) ----
            if not dry_run:
                ContactoWhatsApp.objects.create(
                    cliente=cliente,
                    script=script,
                    eje_valor_snapshot=tax.eje_valor,
                    eje_estilo_snapshot=tax.eje_estilo,
                    eje_contexto_snapshot=tax.eje_contexto,
                    dias_sin_venir_snapshot=tax.dias_desde_ultima_visita,
                    gasto_historico_snapshot=tax.gasto_total or 0,
                    salva=salva,
                    mensaje_renderizado=mensaje,
                    prioridad=prioridad,
                    fecha_sugerido=fecha_obj,
                    estado='pendiente',
                )

            creados += 1
            por_prioridad[prioridad] += 1

            # Guardar primeros 3 para mostrar en reporte (anonimizados)
            if len(sample) < 3:
                tel = cliente.telefono or ''
                tel_anon = (tel[-3:] if len(tel) >= 3 else tel) or 'XXX'
                sample.append({
                    'cliente_id': cliente.id,
                    'nombre_corto': (cliente.nombre or '').split(' ')[0],
                    'tel_anon': f'***{tel_anon}',
                    'eje_valor': tax.eje_valor,
                    'eje_estilo': tax.eje_estilo,
                    'eje_contexto': tax.eje_contexto,
                    'prioridad': prioridad,
                    'salva': salva,
                    'script_id': script.script_id,
                    'mensaje': mensaje,
                })

        return {
            'creados': creados,
            'sin_script': sin_script,
            'agotados': agotados,
            'por_prioridad': dict(por_prioridad),
            'sample': sample,
        }

    # ========================================================================
    # Reporte
    # ========================================================================

    def _reportar(self, r: dict, elapsed: float, dry_run: bool) -> None:
        modo = '(simulación)' if dry_run else '(persistido)'
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f"✓ Bandeja generada: {r['creados']} contactos {modo}"
        ))
        if r['sin_script']:
            self.stdout.write(self.style.WARNING(
                f"  ⚠ {r['sin_script']} candidatos sin script aplicable (ver logs)"
            ))
        if r['agotados']:
            self.stdout.write(
                f"  · {r['agotados']} candidatos ya agotaron sus 3 salvas (saltados)"
            )

        if r['por_prioridad']:
            self.stdout.write('\n  Desglose por prioridad:')
            for p in sorted(r['por_prioridad'].keys()):
                self.stdout.write(
                    f"    [{r['por_prioridad'][p]:>3}]  {PRIORIDAD_LABEL.get(p, f'P{p}')}"
                )

        if r['sample']:
            self.stdout.write('\n  Muestra (3 primeros, anonimizada):')
            for i, s in enumerate(r['sample'], 1):
                self.stdout.write(
                    f"\n    [{i}] cliente_id={s['cliente_id']} {s['nombre_corto']} {s['tel_anon']}"
                )
                self.stdout.write(
                    f"        {s['eje_valor']} · {s['eje_estilo']} · {s['eje_contexto']}"
                )
                self.stdout.write(
                    f"        P{s['prioridad']} · salva {s['salva']} · script [{s['script_id']}]"
                )
                self.stdout.write(f"        ─── mensaje ───")
                for linea in s['mensaje'].split('\n'):
                    self.stdout.write(f"        {linea}")

        self.stdout.write(f"\n  ⏱  {elapsed:.2f}s")
