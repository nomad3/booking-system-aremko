"""Prueba el itinerario Cabaña + Tina (H-015 Nivel 2) sin enviar nada.

Lista las cabañas libres esa noche (siempre para 2), la tina más tarde disponible
(>=16:00), el precio con/ sin descuento de pack (dom-jue) y el desayuno por cabaña.

  python manage.py probar_pack_cabana --fecha 2026-06-17
"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Compone itinerarios Cabaña + Tina de prueba (no envía nada).'

    def add_arguments(self, parser):
        parser.add_argument('--fecha', type=str, required=True, help='Noche de check-in YYYY-MM-DD')

    def handle(self, *args, **opts):
        from whatsapp_agent.packs import disponibilidad_pack_cabana_tina

        res = disponibilidad_pack_cabana_tina(opts['fecha'])
        if res.get('error'):
            raise CommandError(res['error'])

        def clp(n):
            return f"${n:,}".replace(',', '.')

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"— Pack Cabaña + Tina · {res.get('fecha')} · {res.get('personas')} personas —"))
        self.stdout.write(f"  Tina más tarde disponible (>=16:00): {res.get('tina_mas_tarde') or '— (sin tina)'}")

        opciones = res.get('opciones') or []
        if not opciones:
            self.stdout.write(self.style.WARNING(f"  {res.get('nota', 'sin opciones')}"))
            return

        for op in opciones:
            cab = op['cabana']
            self.stdout.write(self.style.HTTP_INFO(f"\n  ▸ {cab['nombre']}"))
            self.stdout.write(self.style.SUCCESS(
                f"    🏠 Cabaña: {clp(cab['precio_total'])} · check-in {cab['hora_check_in']} "
                f"→ check-out {cab['hora_check_out']}"))
            tina = op.get('tina')
            if tina:
                self.stdout.write(self.style.SUCCESS(
                    f"    🛁 Tina: {tina['nombre']} a las {tina['hora']} · {clp(tina['precio_total'])}"))
            else:
                self.stdout.write(self.style.WARNING("    🛁 Tina: sin disponibilidad desde las 16:00"))
            des = op.get('desayuno')
            if des:
                self.stdout.write(
                    f"    🥐 Desayuno (solo si preguntan): {des['nombre']} {clp(des['precio_total'])} "
                    f"para dos · {des['hora']} día siguiente")
            if op.get('hay_descuento'):
                self.stdout.write(self.style.MIGRATE_HEADING(
                    f"    Precio normal: {clp(op['precio_total'])}  →  con pack: "
                    f"{clp(op['precio_con_descuento'])}  (ahorro {clp(op['descuento_pack'])})"))
            else:
                self.stdout.write(self.style.MIGRATE_HEADING(
                    f"    Total: {clp(op['precio_total'])}  (sin descuento de pack aplicable)"))

        if res.get('nota_upsell'):
            self.stdout.write(self.style.HTTP_INFO(f"\n  Upsell: {res['nota_upsell']}"))
