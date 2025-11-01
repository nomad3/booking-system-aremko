"""
Management command para crear tablas Premio y ClientePremio si no existen
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Crear tablas Premio y ClientePremio si no existen'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("🔧 CREANDO TABLAS PREMIO Y CLIENTEPREMIO")
        self.stdout.write("=" * 80)
        self.stdout.write("")

        with connection.cursor() as cursor:
            # Verificar si la tabla ventas_premio existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'ventas_premio'
                );
            """)
            premio_exists = cursor.fetchone()[0]

            if not premio_exists:
                self.stdout.write("⚙️  Creando tabla ventas_premio...")
                cursor.execute("""
                    CREATE TABLE ventas_premio (
                        id SERIAL PRIMARY KEY,
                        tipo VARCHAR(20) NOT NULL,
                        titulo VARCHAR(200) NOT NULL,
                        descripcion_corta TEXT NOT NULL,
                        descripcion_legal TEXT NOT NULL,
                        valor_estimado INTEGER NOT NULL,
                        dias_validez INTEGER NOT NULL,
                        restricciones TEXT NOT NULL,
                        activo BOOLEAN NOT NULL DEFAULT TRUE,
                        imagen VARCHAR(100),
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                        tramo_hito INTEGER NOT NULL DEFAULT 0
                    );
                """)
                self.stdout.write(self.style.SUCCESS("✅ Tabla ventas_premio creada"))
            else:
                self.stdout.write(self.style.SUCCESS("✅ Tabla ventas_premio ya existe"))

            # Verificar si la tabla ventas_clientepremio existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'ventas_clientepremio'
                );
            """)
            cliente_premio_exists = cursor.fetchone()[0]

            if not cliente_premio_exists:
                self.stdout.write("⚙️  Creando tabla ventas_clientepremio...")
                cursor.execute("""
                    CREATE TABLE ventas_clientepremio (
                        id SERIAL PRIMARY KEY,
                        cliente_id INTEGER NOT NULL REFERENCES ventas_cliente(id) ON DELETE CASCADE,
                        premio_id INTEGER NOT NULL REFERENCES ventas_premio(id) ON DELETE CASCADE,
                        codigo_unico VARCHAR(20) NOT NULL UNIQUE,
                        estado VARCHAR(30) NOT NULL,
                        gasto_total_al_ganar DECIMAL(15, 2) NOT NULL,
                        tramo_al_ganar INTEGER NOT NULL,
                        fecha_generacion TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                        fecha_aprobacion TIMESTAMP WITH TIME ZONE,
                        fecha_expiracion DATE NOT NULL,
                        fecha_envio_email TIMESTAMP WITH TIME ZONE,
                        fecha_canje TIMESTAMP WITH TIME ZONE,
                        notas TEXT,
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                    );
                """)

                # Crear índices
                cursor.execute("""
                    CREATE INDEX ventas_clientepremio_cliente_id_idx
                    ON ventas_clientepremio(cliente_id);
                """)
                cursor.execute("""
                    CREATE INDEX ventas_clientepremio_premio_id_idx
                    ON ventas_clientepremio(premio_id);
                """)
                cursor.execute("""
                    CREATE INDEX ventas_clientepremio_estado_idx
                    ON ventas_clientepremio(estado);
                """)
                cursor.execute("""
                    CREATE INDEX ventas_clientepremio_codigo_unico_idx
                    ON ventas_clientepremio(codigo_unico);
                """)

                self.stdout.write(self.style.SUCCESS("✅ Tabla ventas_clientepremio creada con índices"))
            else:
                self.stdout.write(self.style.SUCCESS("✅ Tabla ventas_clientepremio ya existe"))

            # Registrar las migraciones como aplicadas
            self.stdout.write("")
            self.stdout.write("📝 Registrando migraciones en django_migrations...")

            # Registrar migración ficticia para Premio
            cursor.execute("""
                INSERT INTO django_migrations (app, name, applied)
                VALUES ('ventas', '0059_create_premio_tables', NOW())
                ON CONFLICT DO NOTHING;
            """)

            self.stdout.write(self.style.SUCCESS("✅ Migraciones registradas"))

        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("✅ TABLAS PREMIO CREADAS EXITOSAMENTE"))
        self.stdout.write("=" * 80)
