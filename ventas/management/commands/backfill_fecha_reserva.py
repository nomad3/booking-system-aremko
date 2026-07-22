"""
Management command: backfill de fecha_reserva para reservas creadas con el bug H-046.

H-046 (2026-07-22): crear_reserva (aprobación de cotización de Luna / Deborah) no
seteaba fecha_reserva al crear la VentaReserva — quedaba en blanco en el listado
del admin ("-") aunque los servicios de la reserva sí tenían su fecha correcta.
Ya corregido hacia adelante (ver ventas/views/luna_api_views.py). Este comando
repara las filas que quedaron con fecha_reserva vacía ANTES del fix.

Fuente del valor de reemplazo: fecha_creacion (auto_now_add=True) — Django la
llena sola en el instante exacto en que se crea cada fila, sin depender de que
el código la haya pasado bien. En las rutas de creación que sí funcionan
(ventas/views/api_views.py, ventas/services/reservation_service.py) fecha_reserva
se llena con timezone.now() EN EL MISMO INSTANTE que fecha_creacion — por diseño
ambos campos deberían llevar siempre el mismo valor. Por eso fecha_creacion de
cada fila afectada ya contiene el valor real y exacto que fecha_reserva debería
haber tenido — no es una fecha aproximada ni una fecha fija para todas: se copia
fila por fila, cada una con su propio fecha_creacion.

Uso:
    python manage.py backfill_fecha_reserva              # dry-run (solo reporta)
    python manage.py backfill_fecha_reserva --apply       # aplica el cambio real
"""
from django.core.management.base import BaseCommand
from django.db.models import F
from ventas.models import VentaReserva


class Command(BaseCommand):
    help = 'Backfill de fecha_reserva=fecha_creacion para reservas con fecha_reserva vacía (bug H-046)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Aplicar el cambio en la base de datos (default: solo dry-run/reporte)',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("🔧 BACKFILL fecha_reserva (H-046)"))
        self.stdout.write("=" * 80 + "\n")

        if not apply_changes:
            self.stdout.write(self.style.WARNING("⚠️  MODO DRY-RUN: no se harán cambios en la base de datos\n"))

        afectadas = VentaReserva.objects.filter(fecha_reserva__isnull=True).order_by('id')
        total = afectadas.count()

        self.stdout.write(f"📊 Reservas con fecha_reserva vacía: {total:,}\n")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nada que corregir. ✅"))
            return

        self.stdout.write("─" * 80)
        self.stdout.write("🔍 PREVIEW (hasta 20 filas, ordenadas por id)")
        self.stdout.write("─" * 80 + "\n")

        for venta in afectadas[:20]:
            nombre = (venta.cliente.nombre if venta.cliente_id else '(sin cliente)') or '(sin nombre)'
            self.stdout.write(
                f"  #{venta.id:<6} {nombre[:35]:<35} fecha_creacion → {venta.fecha_creacion}"
            )

        if total > 20:
            self.stdout.write(f"  … y {total - 20:,} más\n")
        else:
            self.stdout.write("")

        if apply_changes:
            actualizadas = afectadas.update(fecha_reserva=F('fecha_creacion'))
            self.stdout.write("=" * 80)
            self.stdout.write(self.style.SUCCESS(f"✅ Actualizadas: {actualizadas:,} reservas"))
            self.stdout.write("=" * 80 + "\n")
        else:
            self.stdout.write("=" * 80)
            self.stdout.write(self.style.WARNING(
                f"⚠️  DRY-RUN: {total:,} reservas SERÍAN actualizadas. "
                "Ejecuta con --apply para aplicar el cambio real."
            ))
            self.stdout.write("=" * 80 + "\n")
