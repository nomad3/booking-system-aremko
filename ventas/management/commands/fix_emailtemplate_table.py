# -*- coding: utf-8 -*-
"""
Management command para agregar columnas faltantes a la tabla EmailTemplate
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Agregar columnas faltantes a la tabla EmailTemplate'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("🔧 ACTUALIZANDO TABLA EMAILTEMPLATE")
        self.stdout.write("=" * 80)
        self.stdout.write("")

        with connection.cursor() as cursor:
            # Verificar si la tabla existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'ventas_emailtemplate'
                );
            """)
            table_exists = cursor.fetchone()[0]

            if not table_exists:
                self.stdout.write(self.style.ERROR("❌ La tabla ventas_emailtemplate no existe"))
                self.stdout.write("   Ejecuta primero: python manage.py create_emailtemplate_table")
                return

            # Lista de columnas a verificar/agregar
            columns_to_add = [
                ('name', 'VARCHAR(200) NOT NULL DEFAULT \'\'', 'nombre del template'),
                ('description', 'TEXT NOT NULL DEFAULT \'\'', 'descripción'),
                ('subject_template', 'VARCHAR(500) NOT NULL DEFAULT \'\'', 'asunto del template'),
                ('body_template', 'TEXT NOT NULL DEFAULT \'\'', 'cuerpo HTML del template'),
                ('is_default', 'BOOLEAN NOT NULL DEFAULT FALSE', 'template por defecto'),
                ('is_active', 'BOOLEAN NOT NULL DEFAULT TRUE', 'template activo'),
                ('created_at', 'TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()', 'fecha de creación'),
                ('updated_at', 'TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()', 'fecha de actualización'),
            ]

            for column_name, column_type, description in columns_to_add:
                cursor.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'ventas_emailtemplate'
                    AND column_name = %s;
                """, [column_name])

                if cursor.fetchone() is None:
                    self.stdout.write(f"⚙️  Agregando columna '{column_name}' ({description})...")
                    cursor.execute(f"""
                        ALTER TABLE ventas_emailtemplate
                        ADD COLUMN {column_name} {column_type};
                    """)
                    self.stdout.write(self.style.SUCCESS(f"✅ Columna '{column_name}' agregada"))
                else:
                    self.stdout.write(self.style.SUCCESS(f"✅ Columna '{column_name}' ya existe"))

            # Verificar y agregar columna created_by_id (foreign key) por separado
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'ventas_emailtemplate'
                AND column_name = 'created_by_id';
            """)
            has_created_by = cursor.fetchone() is not None

            if not has_created_by:
                self.stdout.write("⚙️  Agregando columna 'created_by_id'...")
                cursor.execute("""
                    ALTER TABLE ventas_emailtemplate
                    ADD COLUMN created_by_id INTEGER REFERENCES auth_user(id) ON DELETE SET NULL;
                """)
                self.stdout.write(self.style.SUCCESS("✅ Columna 'created_by_id' agregada"))
            else:
                self.stdout.write(self.style.SUCCESS("✅ Columna 'created_by_id' ya existe"))

            # Verificar si existen los índices necesarios
            self.stdout.write("")
            self.stdout.write("🔍 Verificando índices...")

            # Crear índice para created_by_id
            cursor.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'ventas_emailtemplate'
                AND indexname = 'ventas_emailtemplate_created_by_id_idx';
            """)
            if not cursor.fetchone():
                self.stdout.write("⚙️  Creando índice para 'created_by_id'...")
                try:
                    cursor.execute("""
                        CREATE INDEX ventas_emailtemplate_created_by_id_idx
                        ON ventas_emailtemplate(created_by_id);
                    """)
                    self.stdout.write(self.style.SUCCESS("✅ Índice 'created_by_id' creado"))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"⚠️  No se pudo crear índice 'created_by_id': {e}"))

            # Índice is_default
            cursor.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'ventas_emailtemplate'
                AND indexname = 'ventas_emailtemplate_is_default_idx';
            """)
            if not cursor.fetchone():
                self.stdout.write("⚙️  Creando índice para 'is_default'...")
                try:
                    cursor.execute("""
                        CREATE INDEX ventas_emailtemplate_is_default_idx
                        ON ventas_emailtemplate(is_default);
                    """)
                    self.stdout.write(self.style.SUCCESS("✅ Índice 'is_default' creado"))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"⚠️  No se pudo crear índice 'is_default': {e}"))

            # Índice is_active
            cursor.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'ventas_emailtemplate'
                AND indexname = 'ventas_emailtemplate_is_active_idx';
            """)
            if not cursor.fetchone():
                self.stdout.write("⚙️  Creando índice para 'is_active'...")
                try:
                    cursor.execute("""
                        CREATE INDEX ventas_emailtemplate_is_active_idx
                        ON ventas_emailtemplate(is_active);
                    """)
                    self.stdout.write(self.style.SUCCESS("✅ Índice 'is_active' creado"))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"⚠️  No se pudo crear índice 'is_active': {e}"))

        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("✅ TABLA EMAILTEMPLATE ACTUALIZADA EXITOSAMENTE"))
        self.stdout.write("=" * 80)
        self.stdout.write("")
        self.stdout.write("📝 Próximo paso:")
        self.stdout.write("   python manage.py init_email_template")
        self.stdout.write("")
