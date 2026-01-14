# -*- coding: utf-8 -*-
"""
Comando para crear la tabla ventas_servicioslotbloqueo
Migración manual con SQL embebido para bloqueo de slots específicos
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Crea la tabla ventas_servicioslotbloqueo para el sistema de bloqueo de slots'

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
-- MIGRACIÓN MANUAL: Sistema de Bloqueo de Slots Específicos
-- Fecha: 2026-01-14
-- Descripción: Crea tabla para bloquear slots individuales (no días completos)
-- ===============================================================

-- PASO 1: Crear tabla ventas_servicioslotbloqueo
CREATE TABLE IF NOT EXISTS ventas_servicioslotbloqueo (
    id SERIAL PRIMARY KEY,
    servicio_id INTEGER NOT NULL,
    fecha DATE NOT NULL,
    hora_slot VARCHAR(10) NOT NULL,
    motivo VARCHAR(255) NOT NULL,
    creado_por_id INTEGER,
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    notas TEXT,

    -- Constraints
    CONSTRAINT fk_servicioslotbloqueo_servicio
        FOREIGN KEY (servicio_id)
        REFERENCES ventas_servicio(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_servicioslotbloqueo_usuario
        FOREIGN KEY (creado_por_id)
        REFERENCES auth_user(id)
        ON DELETE SET NULL,

    -- Prevenir duplicados: un servicio no puede tener el mismo slot bloqueado dos veces (cuando ambos están activos)
    CONSTRAINT unique_servicio_fecha_slot_activo
        UNIQUE (servicio_id, fecha, hora_slot, activo)
);

-- PASO 2: Crear índices para optimizar consultas
CREATE INDEX IF NOT EXISTS idx_servicioslotbloqueo_servicio
    ON ventas_servicioslotbloqueo(servicio_id);

CREATE INDEX IF NOT EXISTS idx_servicioslotbloqueo_servicio_fecha_hora
    ON ventas_servicioslotbloqueo(servicio_id, fecha, hora_slot);

CREATE INDEX IF NOT EXISTS idx_servicioslotbloqueo_activo
    ON ventas_servicioslotbloqueo(activo);

CREATE INDEX IF NOT EXISTS idx_servicioslotbloqueo_fecha
    ON ventas_servicioslotbloqueo(fecha);

-- PASO 3: Agregar comentarios a la tabla
COMMENT ON TABLE ventas_servicioslotbloqueo IS 'Bloqueos de slots específicos (horarios puntuales, no días completos)';
COMMENT ON COLUMN ventas_servicioslotbloqueo.servicio_id IS 'Servicio que se bloquea';
COMMENT ON COLUMN ventas_servicioslotbloqueo.fecha IS 'Fecha específica del bloqueo (no rango)';
COMMENT ON COLUMN ventas_servicioslotbloqueo.hora_slot IS 'Horario específico a bloquear (ej: 14:30)';
COMMENT ON COLUMN ventas_servicioslotbloqueo.motivo IS 'Razón del bloqueo (Ej: Limpieza, Mantenimiento, Setup)';
COMMENT ON COLUMN ventas_servicioslotbloqueo.activo IS 'Si está activo (permite desbloquear sin eliminar)';
"""

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('MIGRACIÓN: Sistema de Bloqueo de Slots'))
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
            self.stdout.write(self.style.SUCCESS('🔍 Verificando tabla ventas_servicioslotbloqueo...'))

            with connection.cursor() as cursor:
                # Verificar existencia de la tabla
                cursor.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'ventas_servicioslotbloqueo'
                """)
                result = cursor.fetchone()

                if result:
                    self.stdout.write(self.style.SUCCESS('   ✓ Tabla creada correctamente'))

                    # Contar registros
                    cursor.execute("SELECT COUNT(*) FROM ventas_servicioslotbloqueo")
                    count = cursor.fetchone()[0]
                    self.stdout.write(self.style.SUCCESS(f'   ✓ Registros en tabla: {count}'))

                    # Verificar índices
                    cursor.execute("""
                        SELECT indexname
                        FROM pg_indexes
                        WHERE tablename = 'ventas_servicioslotbloqueo'
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
                        WHERE conrelid = 'ventas_servicioslotbloqueo'::regclass
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
            self.stdout.write(self.style.SUCCESS('\n💡 Próximo paso: Crear permisos del modelo'))
            self.stdout.write(self.style.SUCCESS('   python manage.py update_slot_bloqueo_permissions\n'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error ejecutando migración:'))
            self.stdout.write(self.style.ERROR(f'   {str(e)}\n'))
            raise CommandError(f'Migración fallida: {e}')
