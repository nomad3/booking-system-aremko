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

from django.conf import settings
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

        # ---- Acumulación: expirar viejos + arrastrar pendientes del período ----
        # Feature 2026-05-26: contactos en estado='pendiente' de días anteriores
        # se arrastran a fecha_obj para que aparezcan en la bandeja del operador.
        # Los más viejos que OVC_DIAS_MAX_ACUMULACION se marcan como expirados.
        if not dry_run and not cliente_id_filter:
            self._arrastrar_y_expirar_pendientes(fecha_obj)

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
    # Acumulación de pendientes entre días
    # ========================================================================

    def _arrastrar_y_expirar_pendientes(self, fecha_obj: date) -> None:
        """Expira pendientes muy viejos y arrastra el resto a fecha_obj.

        Comportamiento:
          1. Expira (estado='expirado_acumulacion') todo pendiente con
             fecha_sugerido < fecha_obj - OVC_DIAS_MAX_ACUMULACION.
          2. Arrastra (update fecha_sugerido=fecha_obj) todo pendiente en
             [fecha_obj - OVC_DIAS_MAX_ACUMULACION, fecha_obj - 1d].
             Excluye clientes que YA tienen un pendiente en fecha_obj para
             respetar el constraint unique_pendiente_por_cliente_dia.

        Side effects: 2 logs informativos en stdout y logger.

        Notas:
          - Solo se llama cuando NOT dry_run y NOT cliente_id_filter, así
            que el caller ya garantizó modo "cron real".
          - Si OVC_DIAS_MAX_ACUMULACION = 0, expira todo lo pendiente
            anterior a hoy (modo "sin acumulación"). Útil para revertir
            la feature sin redeploy.
        """
        dias_max = getattr(settings, 'OVC_DIAS_MAX_ACUMULACION', 7)
        limite_minimo = fecha_obj - timedelta(days=dias_max)

        # --- Paso 1: expirar muy viejos (< limite_minimo) ---
        muy_viejos = ContactoWhatsApp.objects.filter(
            estado='pendiente',
            fecha_sugerido__lt=limite_minimo,
        )
        n_expirados = muy_viejos.update(estado='expirado_acumulacion')
        if n_expirados > 0:
            self.stdout.write(self.style.WARNING(
                f"  Expirados {n_expirados} pendientes con >{dias_max} días "
                f"(fecha_sugerido < {limite_minimo})"
            ))
            logger.info(
                "Acumulación: expirados %s pendientes con fecha_sugerido < %s",
                n_expirados, limite_minimo,
            )

        # --- Paso 2: arrastrar pendientes del período [limite_minimo, fecha_obj-1] ---
        # Excluir clientes que ya tienen pendiente del día (constraint
        # unique_pendiente_por_cliente_dia los rechazaría con IntegrityError).
        clientes_ya_hoy_ids = list(
            ContactoWhatsApp.objects
            .filter(fecha_sugerido=fecha_obj, estado='pendiente')
            .values_list('cliente_id', flat=True)
        )
        pendientes_periodo = ContactoWhatsApp.objects.filter(
            estado='pendiente',
            fecha_sugerido__gte=limite_minimo,
            fecha_sugerido__lt=fecha_obj,
        ).exclude(cliente_id__in=clientes_ya_hoy_ids)
        n_arrastrados = pendientes_periodo.update(fecha_sugerido=fecha_obj)
        if n_arrastrados > 0:
            self.stdout.write(self.style.NOTICE(
                f"  Arrastrados {n_arrastrados} pendientes de días anteriores "
                f"a {fecha_obj}"
            ))
            logger.info(
                "Acumulación: arrastrados %s pendientes a fecha_sugerido=%s",
                n_arrastrados, fecha_obj,
            )

        # Si quedaron pendientes sin arrastrar por colisión, loguear cuántos
        # (no es un error — son clientes que ya están en la bandeja del día).
        no_arrastrados = ContactoWhatsApp.objects.filter(
            estado='pendiente',
            fecha_sugerido__gte=limite_minimo,
            fecha_sugerido__lt=fecha_obj,
        ).count()
        if no_arrastrados > 0:
            self.stdout.write(
                f"  · {no_arrastrados} pendientes sin arrastrar "
                f"(cliente ya tiene pendiente del día)"
            )

    def _clientes_con_pendiente_hoy(self, fecha_obj: date) -> set:
        """IDs de clientes que ya tienen un ContactoWhatsApp pendiente con
        fecha_sugerido=fecha_obj. Usado para dedupe al generar nuevos.

        Incluye:
          - Pendientes nativos generados en corrida previa del día (raro)
          - Pendientes arrastrados desde días anteriores
        """
        return set(
            ContactoWhatsApp.objects
            .filter(fecha_sugerido=fecha_obj, estado='pendiente')
            .values_list('cliente_id', flat=True)
        )

    # ========================================================================
    # Carga de candidatos
    # ========================================================================

    def _cargar_candidatos(
        self, fecha_obj: date, cliente_id_filter: Optional[int]
    ) -> List[ClienteTaxonomia]:
        """Devuelve lista de ClienteTaxonomia + cliente prefetched que pasan
        los filtros base (opt-out, sin teléfono, gracia, anti-saturación,
        exclusión por nombre staff/proxy)."""

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

        # ──── Etapa Geo.3.a: filtro automático extranjeros ────
        # Clientes con region_geografica='extranjero' NO reciben WhatsApp
        # outbound — el costo de un mensaje internacional + la baja conversión
        # esperada hacen que mejor sean campañas separadas (email, etc).
        # Loguear cuántos se excluyen para auditoría.
        n_antes_extranjero = qs.count()
        qs = qs.exclude(cliente__region_geografica='extranjero')
        n_excluidos_extranjero = n_antes_extranjero - qs.count()
        if n_excluidos_extranjero > 0:
            self.stdout.write(self.style.NOTICE(
                f"  Excluidos por region='extranjero': {n_excluidos_extranjero}"
            ))

        # ──── Etapa 5.5.1: exclusión por nombre staff/proxy ────
        # Aremko Hotel Spa, Jorge Aguilera, Angélica Toloza Poblete, etc.
        # No son personas reales — son "cuentas proxy" donde el staff registra
        # reservas cuando el cliente no se identifica. Si llegan a la bandeja,
        # el sistema les envía mensajes "vuelta a casa" a uno mismo.
        nombres_icontains = getattr(settings, 'OVC_CLIENTES_EXCLUIDOS_ICONTAINS', []) or []
        nombres_iexact = getattr(settings, 'OVC_CLIENTES_EXCLUIDOS_IEXACT', []) or []
        if nombres_icontains or nombres_iexact:
            n_antes = qs.count()
            for patron in nombres_icontains:
                if patron:
                    qs = qs.exclude(cliente__nombre__icontains=patron)
            for patron in nombres_iexact:
                if patron:
                    qs = qs.exclude(cliente__nombre__iexact=patron)
            n_despues = qs.count()
            n_excluidos_nombre = n_antes - n_despues
            if n_excluidos_nombre > 0:
                self.stdout.write(self.style.WARNING(
                    f"  Excluidos por OVC_CLIENTES_EXCLUIDOS_* (staff/proxy): "
                    f"{n_excluidos_nombre} (icontains={nombres_icontains}, "
                    f"iexact={nombres_iexact})"
                ))

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
        duplicados_arrastre = 0
        por_prioridad: Counter = Counter()
        sample: List[dict] = []

        # Dedupe contra pendientes ya en la bandeja del día (arrastrados o
        # generados en corrida previa). Sin esto, generaríamos un nuevo
        # ContactoWhatsApp para un cliente que ya tiene uno pendiente, lo
        # cual viola unique_pendiente_por_cliente_dia → IntegrityError.
        clientes_ya_en_bandeja = (
            self._clientes_con_pendiente_hoy(fecha_obj) if not dry_run else set()
        )

        for tax, prioridad in candidatos_priorizados:
            cliente = tax.cliente

            # ---- Dedupe: cliente ya tiene pendiente del día ----
            if cliente.id in clientes_ya_en_bandeja:
                duplicados_arrastre += 1
                continue

            # ---- Cuántas salvas ya recibió este cliente (en la vida) ----
            salvas_previas = ContactoWhatsApp.objects.filter(
                cliente_id=cliente.id, estado='enviado'
            ).count()
            salva = salvas_previas + 1

            if salva > self.MAX_SALVAS:
                agotados += 1
                continue

            # ---- Buscar script en cascada (Geo.3: con región) ----
            region_cliente = cliente.region_geografica or 'sin_clasificar'
            script = buscar_script_cascada(
                scripts_qs,
                estado_valor=tax.eje_valor,
                estilo=tax.eje_estilo,
                contexto=tax.eje_contexto,
                salva=salva,
                region=region_cliente,
            )
            if script is None:
                sin_script += 1
                logger.warning(
                    "Sin script aplicable: cliente_id=%s estado=%r estilo=%r contexto=%r salva=%s region=%r",
                    cliente.id, tax.eje_valor, tax.eje_estilo, tax.eje_contexto, salva, region_cliente,
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
            'duplicados_arrastre': duplicados_arrastre,
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
        if r.get('duplicados_arrastre'):
            self.stdout.write(
                f"  · {r['duplicados_arrastre']} candidatos ya en bandeja del día (arrastrados o previos)"
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
