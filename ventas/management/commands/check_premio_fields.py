"""
Management command para verificar campos de Premio en la base de datos
"""
from django.core.management.base import BaseCommand
from django.db import connection
from ventas.models import Premio


class Command(BaseCommand):
    help = 'Verifica si existe el campo tramos_validos en la tabla Premio'

    def handle(self, *args, **options):
        self.stdout.write("\n=== VERIFICANDO COLUMNAS DE LA TABLA PREMIO ===\n")

        try:
            with connection.cursor() as cursor:
                # Obtener todas las columnas de la tabla
                cursor.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'ventas_premio'
                    ORDER BY ordinal_position
                """)
                columns = [col[0] for col in cursor.fetchall()]

                self.stdout.write(f"Total de columnas: {len(columns)}")
                self.stdout.write("Columnas encontradas:")
                for col in columns:
                    self.stdout.write(f"  - {col}")

                # Verificar si existe tramos_validos
                if 'tramos_validos' in columns:
                    self.stdout.write(self.style.SUCCESS("\n✅ El campo 'tramos_validos' SÍ existe en la base de datos"))
                else:
                    self.stdout.write(self.style.ERROR("\n❌ El campo 'tramos_validos' NO existe en la base de datos"))
                    self.stdout.write(self.style.WARNING("   Necesitas crear una migración para agregarlo"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error al verificar columnas: {e}"))

        self.stdout.write("\n=== VERIFICANDO DATOS DE PREMIOS ===\n")

        try:
            # Contar premios
            total_premios = Premio.objects.count()
            self.stdout.write(f"Total de premios en la BD: {total_premios}")

            # Verificar todos los premios
            if total_premios > 0:
                for premio in Premio.objects.all():
                    self.stdout.write(f"\nPremio: {premio.nombre}")
                    self.stdout.write(f"  - Tipo: {premio.tipo}")
                    self.stdout.write(f"  - Tramo hito: {premio.tramo_hito}")

                    # Intentar acceder a tramos_validos
                    try:
                        valor_tramos = premio.tramos_validos if premio.tramos_validos else []
                        self.stdout.write(f"  - Tramos válidos: {valor_tramos}")
                    except AttributeError:
                        self.stdout.write(self.style.WARNING("  - Tramos válidos: Campo no existe en el modelo"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  - Tramos válidos: Error al acceder - {e}"))
            else:
                self.stdout.write("No hay premios en la base de datos")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error al verificar premios: {e}"))

        self.stdout.write("\n=== RESUMEN Y PRÓXIMOS PASOS ===\n")
        self.stdout.write("Si el campo 'tramos_validos' no existe en la BD:")
        self.stdout.write("1. Crear archivo de migración manualmente")
        self.stdout.write("2. python manage.py migrate ventas")
        self.stdout.write("3. python manage.py configurar_tramos_premios")