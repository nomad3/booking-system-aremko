# -*- coding: utf-8 -*-
"""Verifica (solo lectura) el fix del bug 'Descuento_Servicios (N personas)' filtrándose al
texto de confirmación de reserva. Reusa la MISMA función que usa el endpoint real de Luna
(GET /api/v1/resumen-reserva/<id>/, ver api/views.py) — no modifica nada.

Uso:
    python manage.py verificar_fix_resumen_descuento 6173 6142
    python manage.py verificar_fix_resumen_descuento  (usa 6173 y 6142 por default, las
                                                        reservas reales donde se vio el bug)
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Verifica que el texto de confirmación ya NO muestre la línea cruda de descuento."

    def add_arguments(self, parser):
        parser.add_argument('reserva_ids', nargs='*', type=int, default=[6173, 6142],
                             help='IDs de reserva a revisar (default: 6173 6142, donde se vio el bug).')

    def handle(self, *args, **opts):
        from ventas.models import VentaReserva, ConfiguracionResumen
        from ventas.views.resumen_reserva_view import _generar_texto_resumen

        ids = opts['reserva_ids'] or [6173, 6142]
        config = ConfiguracionResumen.get_solo()

        for rid in ids:
            reserva = VentaReserva.objects.filter(id=rid).first()
            if not reserva:
                self.stdout.write(self.style.WARNING(f"Reserva {rid}: no existe, se omite."))
                continue
            texto = _generar_texto_resumen(reserva, config)
            tiene_bug = 'personas) - ' in texto and any(
                l.strip().lower().startswith('descuento') and '(' in l and 'persona' in l.lower()
                for l in texto.splitlines()
            )
            self.stdout.write(f"\n{'='*60}\nReserva {rid} ({reserva.cliente.nombre if reserva.cliente else '?'})\n{'='*60}")
            self.stdout.write(texto)
            self.stdout.write(
                self.style.ERROR("\n>>> BUG SIGUE PRESENTE (línea 'Descuento...(N persona)' encontrada)")
                if tiene_bug else
                self.style.SUCCESS("\n>>> OK: sin línea cruda de descuento en 'Servicios contratados'.")
            )
