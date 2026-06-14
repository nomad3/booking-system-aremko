"""Prueba el servicio de disponibilidad del agente (H-011 Fase A) contra datos reales.

Debe coincidir con el "Calendario Matriz de Disponibilidad" del admin. Sirve para
validar el motor reusado antes de conectarlo como herramienta del agente.

Ejemplos (Shell de Render):
  python manage.py probar_disponibilidad --fecha 2026-06-14 --personas 4 --tipo tina
  python manage.py probar_disponibilidad --fecha 2026-06-20 --personas 2
"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Consulta disponibilidad (servicios + horarios libres) por fecha/personas/tipo.'

    def add_arguments(self, parser):
        parser.add_argument('--fecha', type=str, required=True, help='YYYY-MM-DD')
        parser.add_argument('--personas', type=int, default=1)
        parser.add_argument('--tipo', type=str, default='',
                            help='tina | masaje | cabana | otro (vacío = todos)')

    def handle(self, *args, **opts):
        from whatsapp_agent.availability import disponibilidad

        tipo = (opts.get('tipo') or '').strip().lower() or None
        res = disponibilidad(opts['fecha'], opts['personas'], tipo)

        if res.get('error'):
            raise CommandError(res['error'])

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"— Disponibilidad {res['fecha']} · {res['personas']} persona(s) · tipo={res['tipo']} —"))
        servicios = res['servicios']
        if not servicios:
            self.stdout.write(self.style.WARNING('  (sin servicios con cupo/horarios para esos parámetros)'))
            return
        for s in servicios:
            cap = (f"{s['capacidad_minima']}-{s['capacidad_maxima']} pers"
                   if s['capacidad_minima'] != s['capacidad_maxima']
                   else f"{s['capacidad_maxima']} pers")
            self.stdout.write(self.style.SUCCESS(f"  • {s['nombre']} (${s['precio']:,} · {cap})".replace(',', '.')))
            self.stdout.write(f"      horarios libres: {', '.join(s['slots_libres'])}")
