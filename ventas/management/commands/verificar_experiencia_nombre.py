# -*- coding: utf-8 -*-
"""Verifica (solo lectura) que _experiencia_nombre() reconozca 'Noche de Aguas Calientes'
(H-057) en reservas reales de cabaña+tina sin masaje. No modifica nada.

Uso:
    python manage.py verificar_experiencia_nombre 6176
    python manage.py verificar_experiencia_nombre  (usa 6176 por default, la reserva real
                                                     donde Jorge vio el problema)
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Verifica que _experiencia_nombre reconozca los 4 programas en reservas reales."

    def add_arguments(self, parser):
        parser.add_argument('reserva_ids', nargs='*', type=int, default=[6176],
                             help='IDs de reserva a revisar (default: 6176).')

    def handle(self, *args, **opts):
        from ventas.models import VentaReserva
        from ventas.views.ficha_reserva_view import _experiencia_nombre

        for rid in (opts['reserva_ids'] or [6176]):
            venta = VentaReserva.objects.filter(id=rid).first()
            if not venta:
                self.stdout.write(self.style.WARNING(f"Reserva {rid}: no existe, se omite."))
                continue
            tipos = list(
                venta.reservaservicios.select_related('servicio')
                .values_list('servicio__tipo_servicio', flat=True)
            )
            nombre = _experiencia_nombre(tipos)
            self.stdout.write(f"\nReserva {rid}: tipos={tipos}")
            self.stdout.write(
                self.style.SUCCESS(f"  >>> experiencia_nombre = '{nombre}'")
                if nombre else
                self.style.WARNING("  >>> experiencia_nombre = None (servicios sueltos, sin programa)")
            )
