from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = 'Agrega el campo fecha_envio_whatsapp a ClientePremio si la tabla existe'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Verificar si la tabla existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'ventas_clientepremio'
                );
            """)

            table_exists = cursor.fetchone()[0]

            if not table_exists:
                self.stdout.write(
                    self.style.WARNING(
                        "La tabla ventas_clientepremio no existe. "
                        "El modelo Premio no está implementado en producción."
                    )
                )
                return

            # Verificar si la columna ya existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = 'ventas_clientepremio'
                    AND column_name = 'fecha_envio_whatsapp'
                );
            """)

            column_exists = cursor.fetchone()[0]

            if column_exists:
                self.stdout.write(
                    self.style.SUCCESS("El campo fecha_envio_whatsapp ya existe.")
                )
                return

            # Agregar la columna
            try:
                with transaction.atomic():
                    cursor.execute("""
                        ALTER TABLE ventas_clientepremio
                        ADD COLUMN fecha_envio_whatsapp timestamp with time zone NULL;
                    """)

                    self.stdout.write(
                        self.style.SUCCESS(
                            "Campo fecha_envio_whatsapp agregado exitosamente a ventas_clientepremio"
                        )
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error al agregar el campo: {str(e)}")
                )