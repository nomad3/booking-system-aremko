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

        def clp(n):
            return f"${n:,}".replace(',', '.')

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"— Pack Tina + Masaje · {res.get('fecha')} · {res.get('personas')} persona(s) —"))

        opciones = res.get('opciones') or []
        if not opciones:
            self.stdout.write(self.style.WARNING(f"  {res.get('nota', 'sin opciones')}"))
            return

        for op in opciones:
            tina, masaje = op['tina'], op['masaje']
            self.stdout.write(self.style.HTTP_INFO(f"\n  ▸ Opción {op['etiqueta'].upper()}"))
            self.stdout.write(self.style.SUCCESS(
                f"    🛁 Tina: {tina['nombre']} a las {tina['hora']} ({tina['duracion_texto']}) "
                f"· {clp(tina['precio_total'])}"))
            self.stdout.write(self.style.SUCCESS(
                f"    💆 Masaje: {masaje['nombre']} a las {masaje['hora']} (x{masaje['cantidad']}) "
                f"· {clp(masaje['precio_total'])}"))
            self.stdout.write(f"    Orden: {op['orden']}"
                              + ("  (pegado a un masaje ya agendado)" if op['clustering']
                                 else "  (sin masajes ese día → pegado a la tina)"))
            if op.get('hay_descuento'):
                self.stdout.write(self.style.MIGRATE_HEADING(
                    f"    Precio normal: {clp(op['precio_total'])}  →  con pack: "
                    f"{clp(op['precio_con_descuento'])}  (ahorro {clp(op['descuento_pack'])})"))
            else:
                self.stdout.write(self.style.MIGRATE_HEADING(
                    f"    Total: {clp(op['precio_total'])}  (sin descuento de pack aplicable)"))
