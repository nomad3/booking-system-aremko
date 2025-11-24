# -*- coding: utf-8 -*-
"""
Management command para crear tabla CampaignEmailTemplate si no existe
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Crear tabla CampaignEmailTemplate si no existe'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("🔧 CREANDO TABLA CAMPAIGNEMAILTEMPLATE")
        self.stdout.write("=" * 80)
        self.stdout.write("")

        with connection.cursor() as cursor:
            # Verificar si la tabla ventas_campaignemailtemplate existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'ventas_campaignemailtemplate'
                );
            """)
            table_exists = cursor.fetchone()[0]

            if not table_exists:
                self.stdout.write("⚙️  Creando tabla ventas_campaignemailtemplate...")
                cursor.execute("""
                    CREATE TABLE ventas_campaignemailtemplate (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(200) NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        subject_template VARCHAR(500) NOT NULL,
                        body_template TEXT NOT NULL,
                        is_default BOOLEAN NOT NULL DEFAULT FALSE,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                        created_by_id INTEGER REFERENCES auth_user(id) ON DELETE SET NULL
                    );
                """)

                # Crear índices
                cursor.execute("""
                    CREATE INDEX ventas_campaignemailtemplate_is_default_idx
                    ON ventas_campaignemailtemplate(is_default);
                """)
                cursor.execute("""
                    CREATE INDEX ventas_campaignemailtemplate_is_active_idx
                    ON ventas_campaignemailtemplate(is_active);
                """)
                cursor.execute("""
                    CREATE INDEX ventas_campaignemailtemplate_created_by_id_idx
                    ON ventas_campaignemailtemplate(created_by_id);
                """)

                self.stdout.write(self.style.SUCCESS("✅ Tabla ventas_campaignemailtemplate creada con índices"))
            else:
                self.stdout.write(self.style.SUCCESS("✅ Tabla ventas_campaignemailtemplate ya existe"))

            # Registrar la migración como aplicada
            self.stdout.write("")
            self.stdout.write("📝 Registrando migración en django_migrations...")

            cursor.execute("""
                INSERT INTO django_migrations (app, name, applied)
                VALUES ('ventas', '0999_create_campaignemailtemplate_table', NOW())
                ON CONFLICT DO NOTHING;
            """)

            self.stdout.write(self.style.SUCCESS("✅ Migración registrada"))

        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("✅ TABLA CAMPAIGNEMAILTEMPLATE CREADA EXITOSAMENTE"))
        self.stdout.write("=" * 80)
        self.stdout.write("")
        self.stdout.write("📝 Próximos pasos:")
        self.stdout.write("   1. Ejecutar: python manage.py init_email_template")
        self.stdout.write("   2. Configurar templates desde el admin")
        self.stdout.write("")
