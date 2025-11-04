from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Verifica la última migración de ventas aplicada'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT name FROM django_migrations
                WHERE app = 'ventas'
                ORDER BY name DESC
                LIMIT 5
            """)
            migrations = cursor.fetchall()

            self.stdout.write("\nÚltimas 5 migraciones de ventas aplicadas:")
            for migration in migrations:
                self.stdout.write(f"  - {migration[0]}")

            # Verificar específicamente si existe 0059
            cursor.execute("""
                SELECT name FROM django_migrations
                WHERE app = 'ventas' AND name LIKE '0059%'
            """)
            migration_0059 = cursor.fetchone()

            if migration_0059:
                self.stdout.write(f"\nMigración 0059 encontrada: {migration_0059[0]}")
            else:
                self.stdout.write("\n¡ADVERTENCIA! No se encontró ninguna migración 0059")