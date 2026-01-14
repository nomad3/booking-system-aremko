# -*- coding: utf-8 -*-
"""
Comando para ejecutar migraciones SQL manuales de forma segura
"""

import os
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Ejecuta un archivo SQL manual desde migrations_manual/'

    def add_arguments(self, parser):
        parser.add_argument(
            'sql_file',
            type=str,
            help='Nombre del archivo SQL (sin ruta, ej: add_servicio_bloqueo_table.sql)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar el SQL sin ejecutarlo'
        )

    def handle(self, *args, **options):
        sql_filename = options['sql_file']
        dry_run = options['dry_run']

        # Si no tiene extensión, agregarla
        if not sql_filename.endswith('.sql'):
            sql_filename += '.sql'

        # Construir ruta completa
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        sql_file_path = os.path.join(base_dir, 'migrations_manual', sql_filename)

        # Verificar que el archivo existe
        if not os.path.exists(sql_file_path):
            raise CommandError(f'❌ Archivo no encontrado: {sql_file_path}')

        self.stdout.write(self.style.SUCCESS(f'\n📄 Archivo SQL encontrado: {sql_file_path}'))

        # Leer contenido del archivo
        try:
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
        except Exception as e:
            raise CommandError(f'❌ Error leyendo archivo: {e}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  MODO DRY-RUN - No se ejecutará el SQL\n'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(sql_content)
            self.stdout.write(self.style.SUCCESS('=' * 60))
            return

        # Ejecutar SQL
        self.stdout.write(self.style.SUCCESS('\n🚀 Ejecutando migración SQL...'))

        try:
            with connection.cursor() as cursor:
                # Ejecutar el SQL completo
                cursor.execute(sql_content)

                # Intentar obtener resultados si hay (ej: SELECT de verificación)
                try:
                    results = cursor.fetchall()
                    if results:
                        self.stdout.write(self.style.SUCCESS('\n📊 Resultados:'))
                        for row in results:
                            self.stdout.write(f'   {row}')
                except Exception:
                    # No hay resultados, es normal para CREATE TABLE, etc.
                    pass

            self.stdout.write(self.style.SUCCESS('\n✅ Migración ejecutada exitosamente!'))

            # Verificar que la tabla se creó (específico para ServicioBloqueo)
            if 'ventas_serviciobloqueo' in sql_filename.lower() or 'servicio_bloqueo' in sql_filename.lower():
                self.stdout.write(self.style.SUCCESS('\n🔍 Verificando tabla...'))
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = 'ventas_serviciobloqueo'
                    """)
                    result = cursor.fetchone()
                    if result:
                        self.stdout.write(self.style.SUCCESS(f'   ✓ Tabla ventas_serviciobloqueo creada correctamente'))

                        # Contar registros
                        cursor.execute("SELECT COUNT(*) FROM ventas_serviciobloqueo")
                        count = cursor.fetchone()[0]
                        self.stdout.write(self.style.SUCCESS(f'   ✓ Registros en tabla: {count}'))
                    else:
                        self.stdout.write(self.style.WARNING(f'   ⚠ No se pudo verificar la tabla'))

            self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
            self.stdout.write(self.style.SUCCESS('MIGRACIÓN COMPLETADA'))
            self.stdout.write(self.style.SUCCESS('=' * 60 + '\n'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error ejecutando SQL:'))
            self.stdout.write(self.style.ERROR(f'   {str(e)}'))
            raise CommandError(f'Migración fallida: {e}')
