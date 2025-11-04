from django.core.management.base import BaseCommand
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = 'Lista todas las migraciones aplicadas en la base de datos'

    def handle(self, *args, **options):
        self.stdout.write("\n=== MIGRACIONES APLICADAS EN LA BASE DE DATOS ===\n")

        recorder = MigrationRecorder.Migration
        applied_migrations = recorder.objects.all().order_by('app', 'name')

        current_app = None
        for migration in applied_migrations:
            if migration.app != current_app:
                current_app = migration.app
                self.stdout.write(f"\n{self.style.SUCCESS(current_app)}:")

            self.stdout.write(f"  - {migration.name} (aplicada: {migration.applied})")

        # Mostrar específicamente las últimas migraciones de ventas
        self.stdout.write("\n=== ÚLTIMAS 10 MIGRACIONES DE VENTAS ===\n")
        ventas_migrations = recorder.objects.filter(app='ventas').order_by('-name')[:10]

        for migration in ventas_migrations:
            self.stdout.write(f"  - {migration.name}")

        # Verificar si existe 0059_add_tramos_validos
        exists_0059 = recorder.objects.filter(
            app='ventas',
            name='0059_add_tramos_validos'
        ).exists()

        self.stdout.write(f"\n=== VERIFICACIÓN ESPECÍFICA ===")
        self.stdout.write(f"¿Existe 0059_add_tramos_validos? {self.style.SUCCESS('SÍ') if exists_0059 else self.style.ERROR('NO')}")

        # También verificar variantes
        similar_migrations = recorder.objects.filter(
            app='ventas',
            name__contains='0059'
        )
        if similar_migrations.exists():
            self.stdout.write(f"\nMigraciones similares encontradas:")
            for m in similar_migrations:
                self.stdout.write(f"  - {m.name}")