import os
import sys
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
import subprocess


class Command(BaseCommand):
    help = 'Crea un respaldo de la base de datos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='backups/db',
            help='Directorio donde guardar el respaldo'
        )
        parser.add_argument(
            '--format',
            type=str,
            default='custom',
            choices=['custom', 'sql', 'tar'],
            help='Formato del respaldo (custom es más eficiente)'
        )

    def handle(self, *args, **options):
        # Crear directorio si no existe
        output_dir = options['output_dir']
        os.makedirs(output_dir, exist_ok=True)

        # Obtener configuración de la base de datos
        db_config = settings.DATABASES['default']

        if db_config['ENGINE'] != 'django.db.backends.postgresql':
            self.stdout.write(
                self.style.ERROR(
                    'Este comando solo funciona con PostgreSQL'
                )
            )
            return

        # Generar nombre del archivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        db_name = db_config.get('NAME', 'database')

        format_ext = {
            'custom': 'dump',
            'sql': 'sql',
            'tar': 'tar'
        }

        filename = f"{db_name}_backup_{timestamp}.{format_ext[options['format']]}"
        filepath = os.path.join(output_dir, filename)

        # Construir comando pg_dump
        pg_dump_cmd = [
            'pg_dump',
            '-h', db_config.get('HOST', 'localhost'),
            '-p', str(db_config.get('PORT', 5432)),
            '-U', db_config.get('USER', 'postgres'),
            '-d', db_name,
            '-f', filepath,
            '--no-password',
            '--verbose'
        ]

        # Agregar formato
        if options['format'] == 'custom':
            pg_dump_cmd.extend(['-Fc'])  # Formato custom comprimido
        elif options['format'] == 'tar':
            pg_dump_cmd.extend(['-Ft'])  # Formato tar

        # Configurar variable de entorno para password
        env = os.environ.copy()
        if db_config.get('PASSWORD'):
            env['PGPASSWORD'] = db_config['PASSWORD']

        self.stdout.write(
            self.style.WARNING(f"Iniciando respaldo de base de datos...")
        )
        self.stdout.write(f"Base de datos: {db_name}")
        self.stdout.write(f"Host: {db_config.get('HOST', 'localhost')}")
        self.stdout.write(f"Archivo: {filepath}")

        try:
            # Ejecutar pg_dump
            result = subprocess.run(
                pg_dump_cmd,
                env=env,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # Obtener tamaño del archivo
                file_size = os.path.getsize(filepath)
                size_mb = file_size / (1024 * 1024)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n✓ Respaldo completado exitosamente"
                    )
                )
                self.stdout.write(f"Archivo: {filepath}")
                self.stdout.write(f"Tamaño: {size_mb:.2f} MB")

                # Instrucciones para restaurar
                self.stdout.write(
                    self.style.WARNING("\nPara restaurar este respaldo:")
                )

                if options['format'] == 'custom':
                    self.stdout.write(
                        f"pg_restore -h HOST -U USER -d DATABASE {filepath}"
                    )
                else:
                    self.stdout.write(
                        f"psql -h HOST -U USER -d DATABASE < {filepath}"
                    )

            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error al crear respaldo: {result.stderr}"
                    )
                )
                if os.path.exists(filepath):
                    os.remove(filepath)
                sys.exit(1)

        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(
                    "pg_dump no encontrado. Asegúrate de tener PostgreSQL client instalado."
                )
            )
            self.stdout.write(
                "En Ubuntu/Debian: sudo apt-get install postgresql-client"
            )
            self.stdout.write(
                "En MacOS: brew install postgresql"
            )
            sys.exit(1)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error inesperado: {str(e)}")
            )
            if os.path.exists(filepath):
                os.remove(filepath)
            sys.exit(1)