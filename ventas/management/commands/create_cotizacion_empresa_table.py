# -*- coding: utf-8 -*-
"""
Management command para crear tabla CotizacionEmpresa si no existe
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Crear tabla CotizacionEmpresa si no existe'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("🔧 CREANDO TABLA COTIZACIONEMPRESA")
        self.stdout.write("=" * 80)
        self.stdout.write("")

        with connection.cursor() as cursor:
            # Verificar si la tabla ventas_cotizacionempresa existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'ventas_cotizacionempresa'
                );
            """)
            table_exists = cursor.fetchone()[0]

            if not table_exists:
                self.stdout.write("⚙️  Creando tabla ventas_cotizacionempresa...")
                cursor.execute("""
                    CREATE TABLE ventas_cotizacionempresa (
                        id SERIAL PRIMARY KEY,
                        nombre_empresa VARCHAR(200) NOT NULL,
                        nombre_contacto VARCHAR(200) NOT NULL,
                        email VARCHAR(254) NOT NULL,
                        telefono VARCHAR(20) NOT NULL,
                        servicio_interes VARCHAR(50) NOT NULL,
                        numero_personas INTEGER NOT NULL,
                        fecha_tentativa DATE,
                        mensaje_adicional TEXT NOT NULL DEFAULT '',
                        estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
                        notas_internas TEXT NOT NULL DEFAULT '',
                        creado TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                        actualizado TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                        atendido_por_id INTEGER REFERENCES auth_user(id) ON DELETE SET NULL
                    );
                """)
                self.stdout.write(self.style.SUCCESS("✅ Tabla ventas_cotizacionempresa creada"))

                # Crear índices para optimizar consultas
                self.stdout.write("⚙️  Creando índices...")

                cursor.execute("""
                    CREATE INDEX ventas_cotizacionempresa_estado_creado_idx
                    ON ventas_cotizacionempresa(estado, creado DESC);
                """)

                cursor.execute("""
                    CREATE INDEX ventas_cotizacionempresa_fecha_tentativa_idx
                    ON ventas_cotizacionempresa(fecha_tentativa);
                """)

                cursor.execute("""
                    CREATE INDEX ventas_cotizacionempresa_atendido_por_idx
                    ON ventas_cotizacionempresa(atendido_por_id);
                """)

                self.stdout.write(self.style.SUCCESS("✅ Índices creados"))

            else:
                self.stdout.write(self.style.SUCCESS("✅ Tabla ventas_cotizacionempresa ya existe"))

            # Registrar la migración como aplicada
            self.stdout.write("")
            self.stdout.write("📝 Registrando migración en django_migrations...")

            cursor.execute("""
                INSERT INTO django_migrations (app, name, applied)
                VALUES ('ventas', '0999_create_cotizacion_empresa', NOW())
                ON CONFLICT DO NOTHING;
            """)

            self.stdout.write(self.style.SUCCESS("✅ Migración registrada"))

        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("✅ TABLA COTIZACIONEMPRESA CREADA EXITOSAMENTE"))
        self.stdout.write("=" * 80)
        self.stdout.write("")
        self.stdout.write("💡 Ahora puedes usar el modelo CotizacionEmpresa en tu aplicación")
        self.stdout.write("💡 Ejecuta: python manage.py runserver para iniciar el servidor")
        self.stdout.write("")
