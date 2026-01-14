# -*- coding: utf-8 -*-
"""
Comando para crear la tabla ventas_serviciobloqueo
Migración manual con SQL embebido
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Crea la tabla ventas_serviciobloqueo para el sistema de bloqueo de servicios'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar el SQL sin ejecutarlo'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # SQL completo de la migración
        sql_migration = """
-- ===============================================================
-- MIGRACIÓN MANUAL: Sistema de Bloqueo de Servicios
-- Fecha: 2026-01-13
-- Descripción: Crea tabla para bloquear servicios por rangos de fechas
-- ===============================================================

-- PASO 1: Crear tabla ventas_serviciobloqueo
CREATE TABLE IF NOT EXISTS ventas_serviciobloqueo (
    id SERIAL PRIMARY KEY,
    servicio_id INTEGER NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    motivo VARCHAR(255) NOT NULL,
    creado_por_id INTEGER,
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    notas TEXT,

    -- Constraints
    CONSTRAINT fk_serviciobloqueo_servicio
        FOREIGN KEY (servicio_id)
        REFERENCES ventas_servicio(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_serviciobloqueo_usuario
        FOREIGN KEY (creado_por_id)
        REFERENCES auth_user(id)
        ON DELETE SET NULL,

    CONSTRAINT check_fecha_inicio_menor_o_igual_fecha_fin
        CHECK (fecha_inicio <= fecha_fin)
);

-- PASO 2: Crear índices para optimizar consultas
CREATE INDEX IF NOT EXISTS idx_serviciobloqueo_servicio
    ON ventas_serviciobloqueo(servicio_id);

CREATE INDEX IF NOT EXISTS idx_serviciobloqueo_fechas
    ON ventas_serviciobloqueo(servicio_id, fecha_inicio, fecha_fin);

CREATE INDEX IF NOT EXISTS idx_serviciobloqueo_activo
    ON ventas_serviciobloqueo(activo);

CREATE INDEX IF NOT EXISTS idx_serviciobloqueo_fecha_inicio
    ON ventas_serviciobloqueo(fecha_inicio);

CREATE INDEX IF NOT EXISTS idx_serviciobloqueo_fecha_fin
    ON ventas_serviciobloqueo(fecha_fin);

-- PASO 3: Agregar comentarios a la tabla
COMMENT ON TABLE ventas_serviciobloqueo IS 'Bloqueos de servicios por rangos de fechas (mantenimiento, reparaciones, etc)';
COMMENT ON COLUMN ventas_serviciobloqueo.servicio_id IS 'Servicio que se bloquea';
COMMENT ON COLUMN ventas_serviciobloqueo.fecha_inicio IS 'Primer día del bloqueo (inclusive)';
COMMENT ON COLUMN ventas_serviciobloqueo.fecha_fin IS 'Último día del bloqueo (inclusive)';
COMMENT ON COLUMN ventas_serviciobloqueo.motivo IS 'Razón del bloqueo (Ej: Mantenimiento, Reparación)';
COMMENT ON COLUMN ventas_serviciobloqueo.activo IS 'Si está activo (permite desactivar sin eliminar)';
"""

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('MIGRACIÓN: Sistema de Bloqueo de Servicios'))
        self.stdout.write(self.style.SUCCESS('=' * 60 + '\n'))

        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  MODO DRY-RUN - No se ejecutará el SQL\n'))
            self.stdout.write(sql_migration)
            self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
            return

        self.stdout.write(self.style.SUCCESS('🚀 Ejecutando migración SQL...\n'))

        try:
            with connection.cursor() as cursor:
                # Ejecutar el SQL completo
                cursor.execute(sql_migration)

            self.stdout.write(self.style.SUCCESS('✅ SQL ejecutado exitosamente!\n'))

            # Verificar que la tabla se creó
            self.stdout.write(self.style.SUCCESS('🔍 Verificando tabla ventas_serviciobloqueo...'))

            with connection.cursor() as cursor:
                # Verificar existencia de la tabla
                cursor.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'ventas_serviciobloqueo'
                """)
                result = cursor.fetchone()

                if result:
                    self.stdout.write(self.style.SUCCESS('   ✓ Tabla creada correctamente'))

                    # Contar registros
                    cursor.execute("SELECT COUNT(*) FROM ventas_serviciobloqueo")
                    count = cursor.fetchone()[0]
                    self.stdout.write(self.style.SUCCESS(f'   ✓ Registros en tabla: {count}'))

                    # Verificar índices
                    cursor.execute("""
                        SELECT indexname
                        FROM pg_indexes
                        WHERE tablename = 'ventas_serviciobloqueo'
                        ORDER BY indexname
                    """)
                    indices = cursor.fetchall()
                    self.stdout.write(self.style.SUCCESS(f'   ✓ Índices creados: {len(indices)}'))
                    for idx in indices:
                        self.stdout.write(f'      - {idx[0]}')

                    # Verificar constraints
                    cursor.execute("""
                        SELECT conname
                        FROM pg_constraint
                        WHERE conrelid = 'ventas_serviciobloqueo'::regclass
                        ORDER BY conname
                    """)
                    constraints = cursor.fetchall()
                    self.stdout.write(self.style.SUCCESS(f'   ✓ Constraints creados: {len(constraints)}'))
                    for con in constraints:
                        self.stdout.write(f'      - {con[0]}')

                else:
                    raise CommandError('❌ No se pudo crear la tabla')

            self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
            self.stdout.write(self.style.SUCCESS('MIGRACIÓN COMPLETADA EXITOSAMENTE'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(self.style.SUCCESS('\n💡 Ahora puedes usar el sistema de bloqueo de servicios desde:'))
            self.stdout.write(self.style.SUCCESS('   /admin/ventas/serviciobloqueo/\n'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error ejecutando migración:'))
            self.stdout.write(self.style.ERROR(f'   {str(e)}\n'))
            raise CommandError(f'Migración fallida: {e}')
