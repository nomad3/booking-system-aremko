"""Prueba el itinerario Tina + Masaje (H-015 Nivel 1) sin enviar nada.

Compone y muestra el itinerario que propondría el agente para una fecha/personas,
incluido el clustering del masaje (cerca de los masajes ya agendados ese día).

  python manage.py probar_pack --fecha 2026-06-20 --personas 2
"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Compone un itinerario Tina + Masaje de prueba (no envía nada).'

    def add_arguments(self, parser):
        parser.add_argument('--fecha', type=str, required=True, help='YYYY-MM-DD')
        parser.add_argument('--personas', type=int, default=2)

    def handle(self, *args, **opts):
        from whatsapp_agent.packs import disponibilidad_pack_tina_masaje

        res = disponibilidad_pack_tina_masaje(opts['fecha'], opts['personas'])
        if res.get('error'):
            raise CommandError(res['error'])

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"— Pack Tina + Masaje · {res.get('fecha')} · {res.get('personas')} persona(s) —"))

        tina = res.get('tina')
        masaje = res.get('masaje')
        if not tina:
            self.stdout.write(self.style.WARNING(f"  {res.get('nota', 'sin tina')}"))
            return
        if not masaje:
            self.stdout.write(self.style.WARNING(f"  Tina: {tina['nombre']} (horarios: {tina.get('horarios')})"))
            self.stdout.write(self.style.WARNING(f"  {res.get('nota', 'sin masaje')}"))
            return

        self.stdout.write(self.style.SUCCESS(
            f"  🛁 Tina: {tina['nombre']} a las {tina['hora']} ({tina['duracion_texto']}) "
            f"· ${tina['precio_total']:,}".replace(',', '.')))
        self.stdout.write(self.style.SUCCESS(
            f"  💆 Masaje: a las {masaje['hora']} (x{masaje['cantidad']}) "
            f"· ${masaje['precio_total']:,}".replace(',', '.')))
        self.stdout.write(f"  Orden: {res['orden']}"
                          + ("  (pegado a un masaje ya agendado)" if res['clustering']
                             else "  (sin masajes ese día → pegado a la tina)"))
        total = f"${res['precio_total']:,}".replace(',', '.')
        if res.get('hay_descuento'):
            con = f"${res['precio_con_descuento']:,}".replace(',', '.')
            desc = f"${res['descuento_pack']:,}".replace(',', '.')
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"  Precio normal: {total}  →  con pack: {con}  (ahorro {desc})"))
        else:
            self.stdout.write(self.style.MIGRATE_HEADING(f"  Total: {total}  (sin descuento de pack aplicable)"))
