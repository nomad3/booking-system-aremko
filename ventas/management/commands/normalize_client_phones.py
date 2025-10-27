"""
Management command to normalize phone numbers and merge duplicate clients
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from ventas.models import Cliente, VentaReserva, ServiceHistory
from collections import defaultdict


class Command(BaseCommand):
    help = 'Normaliza teléfonos de clientes y fusiona duplicados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué haría sin hacer cambios reales',
        )
        parser.add_argument(
            '--merge-duplicates',
            action='store_true',
            help='Fusiona clientes duplicados después de normalizar',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        merge_duplicates = options['merge_duplicates']

        self.stdout.write(self.style.SUCCESS('\n=== NORMALIZACIÓN DE TELÉFONOS DE CLIENTES ===\n'))

        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: No se harán cambios reales\n'))

        # Paso 1: Normalizar teléfonos
        self.normalize_phones(dry_run)

        # Paso 2: Identificar y fusionar duplicados si se solicita
        if merge_duplicates:
            self.merge_duplicate_clients(dry_run)

        self.stdout.write(self.style.SUCCESS('\n✅ Proceso completado\n'))

    def normalize_phones(self, dry_run):
        """Normaliza todos los teléfonos de clientes"""
        self.stdout.write('\n--- PASO 1: Normalizando teléfonos ---\n')

        clientes = Cliente.objects.all()
        total = clientes.count()
        cambios = 0
        errores = 0

        for i, cliente in enumerate(clientes, 1):
            original = cliente.telefono
            try:
                normalized = Cliente.normalize_phone(cliente.telefono)

                if normalized != original:
                    self.stdout.write(
                        f'[{i}/{total}] Cliente {cliente.id}: '
                        f'{original} → {normalized}'
                    )

                    if not dry_run:
                        # Actualizar sin pasar por save() para evitar duplicate key errors
                        Cliente.objects.filter(id=cliente.id).update(telefono=normalized)

                    cambios += 1
                elif i % 100 == 0:
                    self.stdout.write(f'[{i}/{total}] Procesados...')

            except Exception as e:
                errores += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'[{i}/{total}] Error en cliente {cliente.id} ({cliente.telefono}): {e}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Teléfonos normalizados: {cambios}/{total} '
                f'(Errores: {errores})\n'
            )
        )

    def merge_duplicate_clients(self, dry_run):
        """Identifica y fusiona clientes duplicados por teléfono"""
        self.stdout.write('\n--- PASO 2: Identificando duplicados ---\n')

        # Buscar teléfonos duplicados
        duplicates = (
            Cliente.objects
            .values('telefono')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
        )

        if not duplicates:
            self.stdout.write(self.style.SUCCESS('✓ No se encontraron duplicados\n'))
            return

        self.stdout.write(
            self.style.WARNING(
                f'⚠️  Se encontraron {duplicates.count()} teléfonos con duplicados\n'
            )
        )

        total_fusionados = 0

        for dup in duplicates:
            telefono = dup['telefono']
            clientes_dup = Cliente.objects.filter(telefono=telefono).order_by('created_at')

            self.stdout.write(f'\n📞 Teléfono: {telefono} ({clientes_dup.count()} clientes)')

            # Cliente a mantener (el más antiguo)
            cliente_principal = clientes_dup.first()
            clientes_a_fusionar = list(clientes_dup[1:])

            self.stdout.write(f'   ✓ Mantener: [{cliente_principal.id}] {cliente_principal.nombre}')

            for cliente_dup in clientes_a_fusionar:
                self.stdout.write(
                    f'   ✗ Fusionar: [{cliente_dup.id}] {cliente_dup.nombre}'
                )

            if not dry_run:
                self._merge_clients(cliente_principal, clientes_a_fusionar)
                total_fusionados += len(clientes_a_fusionar)

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Clientes fusionados: {total_fusionados}\n'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'\n⚠️  Clientes que se fusionarían: {len(list(duplicates))} grupos\n'
                )
            )

    @transaction.atomic
    def _merge_clients(self, cliente_principal, clientes_duplicados):
        """
        Fusiona clientes duplicados en uno solo
        """
        for cliente_dup in clientes_duplicados:
            # Mover VentaReserva al cliente principal
            VentaReserva.objects.filter(cliente=cliente_dup).update(
                cliente=cliente_principal
            )

            # Mover ServiceHistory al cliente principal
            try:
                ServiceHistory.objects.filter(cliente=cliente_dup).update(
                    cliente=cliente_principal
                )
            except Exception:
                pass  # ServiceHistory might not exist

            # Actualizar información si el duplicado tiene datos que el principal no tiene
            if not cliente_principal.email and cliente_dup.email:
                cliente_principal.email = cliente_dup.email

            if not cliente_principal.ciudad and cliente_dup.ciudad:
                cliente_principal.ciudad = cliente_dup.ciudad

            if not cliente_principal.pais and cliente_dup.pais:
                cliente_principal.pais = cliente_dup.pais

            # Guardar cambios del principal
            Cliente.objects.filter(id=cliente_principal.id).update(
                email=cliente_principal.email,
                ciudad=cliente_principal.ciudad,
                pais=cliente_principal.pais
            )

            # Eliminar el cliente duplicado
            cliente_dup.delete()

            self.stdout.write(
                self.style.SUCCESS(
                    f'      → Cliente {cliente_dup.id} fusionado y eliminado'
                )
            )
