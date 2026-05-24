"""
cruzar_reservas_contactos_whatsapp
==================================

Cron nocturno (23:30 Santiago) — Operación Vuelta a Casa, Etapa 6.

Atribuye conversiones: para cada VentaReserva creada en las últimas 48 horas,
busca si hubo un ContactoWhatsApp enviado al mismo cliente dentro de los 30
días previos (ventana configurable). Si lo encuentra, marca convirtio=True +
reserva_atribuida + fecha_atribucion.

Esto cierra el loop de medición:
    Cron 06:00  →  generar_bandeja_whatsapp_diaria  →  Deborah envía manual
    Cliente reserva (días después)
    Cron 23:30  →  cruzar_reservas_contactos_whatsapp  →  atribuye conversión

Uso:
    # Producción (cron nocturno):
    python manage.py cruzar_reservas_contactos_whatsapp

    # Backfill un día específico:
    python manage.py cruzar_reservas_contactos_whatsapp --fecha 2026-06-10

    # Simulación sin escribir:
    python manage.py cruzar_reservas_contactos_whatsapp --dry-run

    # Cambiar ventana de atribución (default 30 días):
    python manage.py cruzar_reservas_contactos_whatsapp --ventana-dias 14

Algoritmo:
    1. Resolver ventana de reservas a procesar:
         - Sin --fecha: últimas 48 horas (cubre día actual + día anterior,
           defensivo por si cron del día previo falló)
         - Con --fecha YYYY-MM-DD: reservas creadas en ese día específico

    2. Excluir reservas canceladas (estado_pago='cancelado').

    3. Para cada reserva:
       a. Buscar ContactoWhatsApp del mismo cliente con:
            - estado = 'enviado'
            - fecha_envio entre [reserva.fecha_creacion - ventana_dias,
                                  reserva.fecha_creacion]
              (es decir: enviado ANTES de la reserva, dentro de la ventana)
            - convirtio = False
              (evita doble atribución: si ya fue atribuido a otra reserva,
              no lo tocamos)
       b. Tomar el más reciente (ORDER BY fecha_envio DESC LIMIT 1).
       c. Si no hay match → contar como 'sin_whatsapp', siguiente reserva.
       d. Si hay match → setear convirtio=True, reserva_atribuida=reserva,
          fecha_atribucion=now()

    4. Reportar conteos: atribuidas, sin_whatsapp, ya_atribuidas (reservas
       que tenían atribución previa de un cron anterior).

Idempotencia:
    - Si se corre 2 veces sobre el mismo día, la segunda no atribuye nuevamente
      porque el contacto ya tiene convirtio=True (filtro lo excluye).
    - Si una reserva ya fue atribuida previamente y aparece otro contacto
      candidato, NO se le quita el primer enlace (preserva auditoría).
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from ventas.models import ContactoWhatsApp, VentaReserva


class Command(BaseCommand):
    help = (
        "Atribuye conversiones: para cada VentaReserva reciente, busca el último "
        "ContactoWhatsApp enviado al cliente dentro de la ventana y lo marca como "
        "convertido. Diseñado para correr como cron nocturno (23:30 Santiago)."
    )

    DEFAULT_VENTANA_DIAS = 30
    DEFAULT_HORAS_RETROACTIVAS = 48  # cubre día actual + día anterior

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='No escribe a DB. Solo reporta qué pasaría.',
        )
        parser.add_argument(
            '--fecha', type=str, default=None,
            help=(
                'Procesar SOLO reservas creadas en este día (YYYY-MM-DD). '
                'Útil para backfill. Sin este flag, procesa últimas 48 horas.'
            ),
        )
        parser.add_argument(
            '--ventana-dias', type=int, default=self.DEFAULT_VENTANA_DIAS,
            help=(
                f'Ventana hacia atrás (en días) desde fecha de reserva para '
                f'buscar el WhatsApp atribuible. Default {self.DEFAULT_VENTANA_DIAS}.'
            ),
        )

    # ========================================================================
    # Entry point
    # ========================================================================

    def handle(self, *args, **opts):
        t0 = time.time()
        dry_run = opts['dry_run']
        ventana_dias = opts['ventana_dias']
        fecha_str = opts['fecha']

        if ventana_dias < 1:
            raise CommandError(f"--ventana-dias debe ser >= 1, recibí {ventana_dias}")

        # ---- Resolver rango de reservas a procesar ----
        if fecha_str:
            try:
                fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                raise CommandError(
                    f"--fecha inválido: '{fecha_str}'. Formato esperado YYYY-MM-DD."
                )
            # Reservas creadas en ese día específico (00:00 a 23:59:59)
            tz = timezone.get_current_timezone()
            desde_dt = timezone.make_aware(
                datetime.combine(fecha_obj, datetime.min.time()), tz,
            )
            hasta_dt = desde_dt + timedelta(days=1)
            modo_descripcion = f"día específico {fecha_obj.isoformat()}"
        else:
            # Default: últimas 48 horas
            hasta_dt = timezone.now()
            desde_dt = hasta_dt - timedelta(hours=self.DEFAULT_HORAS_RETROACTIVAS)
            modo_descripcion = (
                f"últimas {self.DEFAULT_HORAS_RETROACTIVAS} horas "
                f"({desde_dt.isoformat()} → {hasta_dt.isoformat()})"
            )

        self.stdout.write(self.style.NOTICE(
            f"Cruzar reservas → contactos WhatsApp · {modo_descripcion} "
            f"· ventana atribución: {ventana_dias}d "
            f"{'(DRY-RUN)' if dry_run else '(escribiendo)'}"
        ))

        # ---- Cargar reservas a procesar ----
        reservas = (
            VentaReserva.objects
            .filter(fecha_creacion__gte=desde_dt, fecha_creacion__lt=hasta_dt)
            .exclude(estado_pago='cancelado')
            .select_related('cliente')
            .order_by('fecha_creacion')
        )
        total_reservas = reservas.count()
        self.stdout.write(f"  Reservas en rango: {total_reservas}")

        # ---- Procesar ----
        atribuidas = 0
        sin_whatsapp = 0
        ya_atribuidas = 0  # reserva con whatsapp_atribuidos pre-existente
        sample = []

        for reserva in reservas:
            if reserva.cliente_id is None:
                sin_whatsapp += 1
                continue

            # ¿Esta reserva ya tiene algún contacto atribuido previamente?
            ya_existe_atribucion = ContactoWhatsApp.objects.filter(
                reserva_atribuida=reserva
            ).exists()
            if ya_existe_atribucion:
                ya_atribuidas += 1
                continue

            # Buscar el contacto candidato
            corte_min = reserva.fecha_creacion - timedelta(days=ventana_dias)
            contacto = (
                ContactoWhatsApp.objects
                .filter(
                    cliente_id=reserva.cliente_id,
                    estado='enviado',
                    fecha_envio__gte=corte_min,
                    fecha_envio__lte=reserva.fecha_creacion,
                    convirtio=False,
                )
                .order_by('-fecha_envio')
                .first()
            )
            if contacto is None:
                sin_whatsapp += 1
                continue

            # Atribuir
            if not dry_run:
                contacto.convirtio = True
                contacto.reserva_atribuida = reserva
                contacto.fecha_atribucion = timezone.now()
                contacto.save(update_fields=[
                    'convirtio', 'reserva_atribuida', 'fecha_atribucion',
                ])

            atribuidas += 1

            # Sample para reporte (3 primeros, anonimizados)
            if len(sample) < 3:
                cli = reserva.cliente
                tel = cli.telefono or ''
                tel_anon = (tel[-3:] if len(tel) >= 3 else tel) or 'XXX'
                gap_dias = (reserva.fecha_creacion - contacto.fecha_envio).days
                sample.append({
                    'cliente_id': cli.id,
                    'nombre': (cli.nombre or '').split(' ')[0],
                    'tel_anon': f'***{tel_anon}',
                    'reserva_id': reserva.id,
                    'reserva_total': reserva.total,
                    'contacto_id': contacto.id,
                    'script_id': contacto.script.script_id if contacto.script else '',
                    'gap_dias': gap_dias,
                })

        # ---- Reporte ----
        elapsed = time.time() - t0
        self._reportar(
            total_reservas=total_reservas,
            atribuidas=atribuidas,
            sin_whatsapp=sin_whatsapp,
            ya_atribuidas=ya_atribuidas,
            sample=sample,
            elapsed=elapsed,
            dry_run=dry_run,
        )

    # ========================================================================
    # Reporte
    # ========================================================================

    def _reportar(self, *, total_reservas, atribuidas, sin_whatsapp,
                  ya_atribuidas, sample, elapsed, dry_run):
        modo = '(simulación)' if dry_run else '(persistido)'
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f"✓ Atribuciones: {atribuidas} {modo}"
        ))
        self.stdout.write(
            f"  · {sin_whatsapp} reservas sin WhatsApp atribuible en ventana"
        )
        if ya_atribuidas:
            self.stdout.write(
                f"  · {ya_atribuidas} reservas ya tenían atribución previa (saltadas)"
            )

        if total_reservas > 0:
            tasa = atribuidas / total_reservas * 100
            self.stdout.write(f"  · Tasa de atribución: {tasa:.1f}%")

        if sample:
            self.stdout.write('\n  Muestra de atribuciones (anonimizada):')
            for i, s in enumerate(sample, 1):
                gap_str = (
                    f"{s['gap_dias']}d después del WhatsApp"
                    if s['gap_dias'] > 0
                    else "mismo día del WhatsApp"
                )
                self.stdout.write(
                    f"    [{i}] cliente_id={s['cliente_id']} {s['nombre']} {s['tel_anon']}"
                    f"  reserva #{s['reserva_id']} (${s['reserva_total']:,.0f})"
                    f"  ← script [{s['script_id']}] · {gap_str}"
                )

        self.stdout.write(f"\n  ⏱  {elapsed:.2f}s")
