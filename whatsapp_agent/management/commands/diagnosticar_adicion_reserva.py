# -*- coding: utf-8 -*-
"""Diagnóstico de agregar servicio/producto a una reserva YA CREADA (H-060).

Dos modos, ambos seguros (no dejan cambios reales en la BD):

1. --telefono X: muestra las reservas ELEGIBLES de ese cliente (buscar_reservas_elegibles),
   solo lectura, sin ningún efecto secundario.

2. --simular-adicion RESERVA_ID (+ --servicio-id/--fecha/--hora/--personas, o
   --producto-id/--cantidad): corre agregar_items_a_reserva() de VERDAD contra esa
   reserva real, pero DENTRO de una transacción que se revierte al final (savepoint +
   rollback explícito) — muestra el ANTES/DESPUÉS de total/saldo_pendiente/estado_pago
   (para confirmar el fix del bug: una reserva 'pagado' debe bajar a 'parcial' si el
   nuevo total supera lo pagado) sin persistir nada.

Uso:
    python manage.py diagnosticar_adicion_reserva --telefono +56912345678
    python manage.py diagnosticar_adicion_reserva --simular-adicion 6037 \\
        --servicio-id 9 --fecha 2026-07-10 --hora 16:00 --personas 2
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "H-060: diagnóstico de solo lectura (con simulación revertida) de agregar a una reserva existente."

    def add_arguments(self, parser):
        parser.add_argument('--telefono', type=str, default=None,
                            help='Muestra las reservas elegibles de este teléfono (solo lectura)')
        parser.add_argument('--simular-adicion', type=int, default=None, dest='reserva_id',
                            help='ID de una VentaReserva real para simular una adición (se revierte, no se guarda)')
        parser.add_argument('--servicio-id', type=int, default=None)
        parser.add_argument('--fecha', type=str, default=None, help='YYYY-MM-DD')
        parser.add_argument('--hora', type=str, default=None, help='HH:MM')
        parser.add_argument('--personas', type=int, default=1)
        parser.add_argument('--producto-id', type=int, default=None)
        parser.add_argument('--cantidad', type=int, default=1)

    def handle(self, *args, **opts):
        if opts.get('telefono'):
            self._mostrar_reservas_elegibles(opts['telefono'])
        if opts.get('reserva_id'):
            self._simular_adicion(opts)
        if not opts.get('telefono') and not opts.get('reserva_id'):
            self.stdout.write(self.style.ERROR(
                'Pasá --telefono X o --simular-adicion RESERVA_ID (ver --help)'))

    def _mostrar_reservas_elegibles(self, telefono):
        from whatsapp_agent.reserva_service import buscar_reservas_elegibles

        self.stdout.write(f'=== Reservas elegibles para {telefono} ===')
        elegibles = buscar_reservas_elegibles(telefono)
        if not elegibles:
            self.stdout.write('  (ninguna)')
        for r in elegibles:
            self.stdout.write(
                f"  [{r['reserva_id']}] {r['numero']} — {r['resumen_corto']} · "
                f"estado_pago={r['estado_pago']} · total=${r['total']:,.0f} · "
                f"fecha_principal={r['fecha_principal']}"
            )

    def _simular_adicion(self, opts):
        from ventas.models import VentaReserva
        from ventas.services.reserva_addition_service import agregar_items_a_reserva

        reserva_id = opts['reserva_id']
        try:
            venta_antes = VentaReserva.objects.get(id=reserva_id)
        except VentaReserva.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Reserva {reserva_id} no existe'))
            return

        self.stdout.write(f'\n=== ANTES de simular adición a reserva {reserva_id} ===')
        self.stdout.write(
            f"  total=${venta_antes.total:,.0f} · pagado=${venta_antes.pagado:,.0f} · "
            f"saldo_pendiente=${venta_antes.saldo_pendiente:,.0f} · estado_pago={venta_antes.estado_pago!r}"
        )

        servicios_data = []
        if opts.get('servicio_id'):
            servicios_data.append({
                'servicio_id': opts['servicio_id'], 'fecha': opts['fecha'],
                'hora': opts['hora'], 'cantidad_personas': opts['personas'],
            })
        productos_data = []
        if opts.get('producto_id'):
            productos_data.append({'producto_id': opts['producto_id'], 'cantidad': opts['cantidad']})

        if not servicios_data and not productos_data:
            self.stdout.write(self.style.ERROR(
                'Pasá --servicio-id (+ --fecha --hora --personas) o --producto-id (+ --cantidad)'))
            return

        self.stdout.write('\n=== Simulando agregar_items_a_reserva (se revierte, NO se guarda) ===')
        try:
            with transaction.atomic():
                resultado = agregar_items_a_reserva(venta_antes, servicios_data, productos_data)
                venta_antes.refresh_from_db()
                self.stdout.write(
                    f"  DESPUÉS (simulado): total=${venta_antes.total:,.0f} · "
                    f"pagado=${venta_antes.pagado:,.0f} · "
                    f"saldo_pendiente=${venta_antes.saldo_pendiente:,.0f} · "
                    f"estado_pago={venta_antes.estado_pago!r}"
                )
                self.stdout.write(f"  servicios_agregados: {resultado['servicios_agregados']}")
                self.stdout.write(f"  productos_agregados: {resultado['productos_agregados']}")
                self.stdout.write(f"  descuentos_aplicados: {resultado['descuentos_aplicados']}")
                # Revertir SIEMPRE — esto es una simulación, no debe dejar datos reales.
                raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING(
                '\n  (revertido — no se guardó nada en la base de datos real)'))
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.ERROR(f'\n  Error simulando: {exc}'))


class _Rollback(Exception):
    """Señal interna para forzar rollback de la transacción de simulación."""
    pass
