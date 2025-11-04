from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Verifica rápidamente la última migración aplicada de ventas'

    def handle(self, *args, **options):
        try:
            with connection.cursor() as cursor:
                # Verificar si la tabla existe
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'django_migrations'
                    );
                """)
                if not cursor.fetchone()[0]:
                    self.stdout.write("ERROR: La tabla django_migrations no existe")
                    return

                # Obtener la última migración
                cursor.execute("""
                    SELECT name FROM django_migrations
                    WHERE app = 'ventas'
                    ORDER BY id DESC
                    LIMIT 1
                """)
                result = cursor.fetchone()

                if result:
                    self.stdout.write(f"ÚLTIMA MIGRACIÓN DE VENTAS: {result[0]}")
                else:
                    self.stdout.write("No hay migraciones de ventas aplicadas")

        except Exception as e:
            self.stdout.write(f"ERROR: {str(e)}")