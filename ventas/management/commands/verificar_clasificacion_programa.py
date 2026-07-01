# -*- coding: utf-8 -*-
"""Verifica (solo lectura) clasificar_ventareservas_por_programa() contra reservas reales
conocidas, antes de confiar en la columna "Programa" de /venta_reservas/ (H-058).
No modifica nada.

Uso:
    python manage.py verificar_clasificacion_programa 6176 6173 6142
    python manage.py verificar_clasificacion_programa   (usa algunas reservas recientes)
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Imprime a qué programa clasifica cada VentaReserva dada (o las más recientes)."

    def add_arguments(self, parser):
        parser.add_argument('reserva_ids', nargs='*', type=int)

    def handle(self, *args, **opts):
        from ventas.models import VentaReserva
        from ventas.api_aremko_cli import clasificar_ventareservas_por_programa, PROGRAMA_LABELS

        ids = opts['reserva_ids']
        if not ids:
            ids = list(
                VentaReserva.objects.order_by('-fecha_creacion').values_list('id', flat=True)[:10]
            )
            self.stdout.write(f"Sin IDs indicados — usando las 10 reservas más recientes: {ids}")

        clasificacion = clasificar_ventareservas_por_programa(ids)
        nombres = dict(PROGRAMA_LABELS)

        for rid in ids:
            venta = VentaReserva.objects.filter(id=rid).first()
            if not venta:
                self.stdout.write(self.style.WARNING(f"Reserva {rid}: no existe, se omite."))
                continue
            tipos = list(
                venta.reservaservicios.select_related('servicio')
                .values_list('servicio__tipo_servicio', flat=True)
            )
            programa = clasificacion.get(rid, 'otros')
            self.stdout.write(f"\nReserva {rid}: tipos={tipos}")
            self.stdout.write(
                self.style.SUCCESS(f"  >>> programa = {nombres.get(programa, programa)} ({programa})")
            )
