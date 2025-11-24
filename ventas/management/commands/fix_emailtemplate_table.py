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

            # Verificar y agregar columna description si no existe
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'ventas_emailtemplate'
                AND column_name = 'description';
            """)
            has_description = cursor.fetchone() is not None

            if not has_description:
                self.stdout.write("⚙️  Agregando columna 'description'...")
                cursor.execute("""
                    ALTER TABLE ventas_emailtemplate
                    ADD COLUMN description TEXT NOT NULL DEFAULT '';
                """)
                self.stdout.write(self.style.SUCCESS("✅ Columna 'description' agregada"))
            else:
                self.stdout.write(self.style.SUCCESS("✅ Columna 'description' ya existe"))

            # Verificar y agregar columna is_active si no existe
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'ventas_emailtemplate'
                AND column_name = 'is_active';
            """)
            has_is_active = cursor.fetchone() is not None

            if not has_is_active:
                self.stdout.write("⚙️  Agregando columna 'is_active'...")
                cursor.execute("""
                    ALTER TABLE ventas_emailtemplate
                    ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;
                """)
                self.stdout.write(self.style.SUCCESS("✅ Columna 'is_active' agregada"))
            else:
                self.stdout.write(self.style.SUCCESS("✅ Columna 'is_active' ya existe"))

            # Verificar y agregar columna created_by_id si no existe
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
                # Crear índice
                cursor.execute("""
                    CREATE INDEX ventas_emailtemplate_created_by_id_idx
                    ON ventas_emailtemplate(created_by_id);
                """)
                self.stdout.write(self.style.SUCCESS("✅ Columna 'created_by_id' agregada con índice"))
            else:
                self.stdout.write(self.style.SUCCESS("✅ Columna 'created_by_id' ya existe"))

            # Verificar si existen los índices necesarios
            self.stdout.write("")
            self.stdout.write("🔍 Verificando índices...")

            # Índice is_default
            cursor.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'ventas_emailtemplate'
                AND indexname = 'ventas_emailtemplate_is_default_idx';
            """)
            if not cursor.fetchone():
                self.stdout.write("⚙️  Creando índice para 'is_default'...")
                cursor.execute("""
                    CREATE INDEX ventas_emailtemplate_is_default_idx
                    ON ventas_emailtemplate(is_default);
                """)
                self.stdout.write(self.style.SUCCESS("✅ Índice 'is_default' creado"))

            # Índice is_active
            cursor.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'ventas_emailtemplate'
                AND indexname = 'ventas_emailtemplate_is_active_idx';
            """)
            if not cursor.fetchone():
                self.stdout.write("⚙️  Creando índice para 'is_active'...")
                cursor.execute("""
                    CREATE INDEX ventas_emailtemplate_is_active_idx
                    ON ventas_emailtemplate(is_active);
                """)
                self.stdout.write(self.style.SUCCESS("✅ Índice 'is_active' creado"))

        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("✅ TABLA EMAILTEMPLATE ACTUALIZADA EXITOSAMENTE"))
        self.stdout.write("=" * 80)
        self.stdout.write("")
        self.stdout.write("📝 Próximo paso:")
        self.stdout.write("   python manage.py init_email_template")
        self.stdout.write("")
