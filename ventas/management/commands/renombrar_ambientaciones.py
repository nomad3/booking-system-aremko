"""AR-016: renombra las 4 ambientaciones de cumpleaños eliminando "Dama/Varón".

Uso:
    python manage.py renombrar_ambientaciones          # dry-run
    python manage.py renombrar_ambientaciones --apply  # aplica cambios

Idempotente: si el nombre ya fue cambiado, lo deja como está.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from ventas.models import Servicio


# (matcher_lowercase_substrings, nombre_nuevo)
# El matcher busca fragmentos que deben estar TODOS presentes en nombre.lower(),
# para evitar colisiones con otros servicios de cumpleaños futuros.
RENAMES = [
    (('cumpleaños', 'c1', 'varon'), 'Decoración Cumpleaños · Azul'),
    (('cumpleaños', 'c1', 'dama'),  'Decoración Cumpleaños · Rosado'),
    (('cumpleaños', 'c2', 'varon'), 'Decoración Cumpleaños con Torta · Azul'),
    (('cumpleaños', 'c2', 'dama'),  'Decoración Cumpleaños con Torta · Rosado'),
]


class Command(BaseCommand):
    help = 'AR-016: renombra ambientaciones de cumpleaños a nombres inclusivos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Aplica los cambios. Sin esta flag se ejecuta en modo dry-run.',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']
        modo = 'APLICANDO' if apply_changes else 'DRY-RUN'
        self.stdout.write(self.style.WARNING(f'=== {modo} AR-016: renombrar ambientaciones ==='))

        with transaction.atomic():
            cambios = 0
            no_encontrados = []

            for matchers, nombre_nuevo in RENAMES:
                qs = Servicio.objects.all()
                for m in matchers:
                    qs = qs.filter(nombre__icontains=m)

                # Excluir los que ya tienen el nombre nuevo (idempotencia)
                matches = [s for s in qs if s.nombre != nombre_nuevo]

                if not matches:
                    # Revisar si ya fue renombrado
                    ya = Servicio.objects.filter(nombre=nombre_nuevo).first()
                    if ya:
                        self.stdout.write(
                            f'  ✓ Ya renombrado: "{nombre_nuevo}" (id={ya.id})'
                        )
                    else:
                        no_encontrados.append((matchers, nombre_nuevo))
                        self.stdout.write(self.style.ERROR(
                            f'  ✗ No encontrado: fragmentos {matchers}'
                        ))
                    continue

                if len(matches) > 1:
                    self.stdout.write(self.style.ERROR(
                        f'  ✗ Ambiguo: {len(matches)} matches para {matchers}:'
                    ))
                    for s in matches:
                        self.stdout.write(f'      id={s.id}  nombre="{s.nombre}"')
                    continue

                servicio = matches[0]
                nombre_viejo = servicio.nombre
                self.stdout.write(
                    f'  → id={servicio.id}: "{nombre_viejo}" => "{nombre_nuevo}"'
                )
                if apply_changes:
                    servicio.nombre = nombre_nuevo
                    servicio.save(update_fields=['nombre'])
                cambios += 1

            if not apply_changes:
                # Forzar rollback explícito en dry-run
                transaction.set_rollback(True)

        self.stdout.write('')
        if apply_changes:
            self.stdout.write(self.style.SUCCESS(
                f'Listo. {cambios} servicio(s) renombrado(s).'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'Dry-run: {cambios} servicio(s) se renombrarían. '
                f'Ejecuta con --apply para confirmar.'
            ))

        if no_encontrados:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(
                'Advertencia: algunos registros no fueron encontrados. '
                'Revisa los nombres actuales en admin antes de re-ejecutar.'
            ))
