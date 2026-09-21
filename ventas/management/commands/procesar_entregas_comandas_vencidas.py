"""
procesar_entregas_comandas_vencidas
===================================

Descuenta inventario de comandas cuya fecha de entrega objetivo ya llegó pero
que aún NO fueron marcadas como 'entregada'.

Regla de negocio (Operación inventario): el stock de los productos de una comanda
se descuenta recién cuando la comanda se ENTREGA o cuando llega su fecha objetivo
(lo que ocurra primero). Una comanda con entrega planificada en 10 días no debe
tocar el inventario hasta ese día.

Este comando cubre el segundo disparador (la fecha llegó sin marcar entregada):
busca comandas confirmadas y vencidas, y setea fecha_entrega en sus
ReservaProducto pendientes, lo que dispara el descuento de stock vía signal.

Idempotente: solo toca ReservaProducto con fecha_entrega NULL; los ya descontados
se omiten. Correr a diario (cron-job.org, 06:30, desde el 21-09-2026).

Y CIERRA la comanda como 'entregada' (21-09-2026). Hasta entonces solo descontaba
el stock y dejaba la comanda 'pendiente': nunca había corrido en producción, y
la primera pasada real (37 comandas acumuladas desde agosto) las descontó y las
dejó todas pendientes, para volver a encontrarlas al día siguiente y para que
cocina y la agenda las siguieran mostrando como si faltara prepararlas.

Uso:
    python manage.py procesar_entregas_comandas_vencidas
    python manage.py procesar_entregas_comandas_vencidas --dry-run
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from ventas.models import Comanda


# Comandas confirmadas a la espera de entrega (NO borrador / pendiente_pago /
# cancelada / pago_fallido / entregada).
ESTADOS_ACTIVOS = ('pendiente', 'procesando', 'pago_confirmado')


class Command(BaseCommand):
    help = (
        "Descuenta inventario de comandas cuya fecha de entrega objetivo ya "
        "venció y que aún no se marcaron como 'entregada'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='No descuenta; solo informa qué comandas se procesarían.',
        )

    def handle(self, *args, **opts):
        dry_run = opts['dry_run']
        ahora = timezone.now()
        hoy = ahora.date()

        comandas = (
            Comanda.objects
            .filter(
                estado__in=ESTADOS_ACTIVOS,
                fecha_entrega_objetivo__isnull=False,
                fecha_entrega_objetivo__lte=ahora,
                venta_reserva__isnull=False,
            )
            .select_related('venta_reserva')
        )

        total_comandas = 0
        total_lineas = 0
        for comanda in comandas:
            pendientes = comanda.detalles.count()
            if dry_run:
                self.stdout.write(
                    f"  [DRY] Comanda #{comanda.id} (objetivo "
                    f"{comanda.fecha_entrega_objetivo:%Y-%m-%d %H:%M}, "
                    f"estado={comanda.estado}) → {pendientes} detalle(s)"
                )
                total_comandas += 1
                continue
            marcadas = comanda.entregar_inventario(fecha=hoy)
            # Cerrarla igual que el botón de la agenda: entregada, con su hora. Va por
            # `.update()` a propósito: pasar por Comanda.save() volvería a llamar a
            # entregar_inventario() (inofensivo, pero es trabajo doble). El stock ya se
            # movió arriba, línea por línea, con el reparto por cantidad.
            Comanda.objects.filter(pk=comanda.pk).update(
                estado='entregada', fecha_entrega=ahora,
                notas_generales=((comanda.notas_generales or '').rstrip() +
                                 f"\n[{timezone.localtime(ahora):%d/%m/%Y %H:%M}] Dada por entregada "
                                 "automáticamente: su hora objetivo pasó y nadie la marcó.").strip())
            total_comandas += 1
            total_lineas += marcadas
            self.stdout.write(
                f"  Comanda #{comanda.id}: cerrada; {marcadas} línea(s) descontadas de inventario"
            )

        modo = ' (DRY-RUN)' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f"✓ Entregas por vencimiento procesadas{modo}: "
            f"{total_comandas} comanda(s) cerradas, {total_lineas} línea(s) descontadas."
        ))
