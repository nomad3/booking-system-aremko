-- Script SQL para crear la tabla PackDescuento

-- Verificar si la tabla ya existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name = 'ventas_packdescuento'
    ) THEN
        -- Crear la tabla
        CREATE TABLE ventas_packdescuento (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(200) NOT NULL,
            descripcion TEXT NOT NULL,
            descuento DECIMAL(10, 0) NOT NULL,
            servicios_requeridos JSONB NOT NULL DEFAULT '[]'::jsonb,
            dias_semana_validos JSONB NOT NULL DEFAULT '[]'::jsonb,
            activo BOOLEAN NOT NULL DEFAULT true,
            fecha_inicio DATE NOT NULL,
            fecha_fin DATE NULL,
            prioridad INTEGER NOT NULL DEFAULT 0,
            cantidad_minima_noches INTEGER NOT NULL DEFAULT 1,
            misma_fecha BOOLEAN NOT NULL DEFAULT true
        );

        -- Crear índices
        CREATE INDEX idx_pack_descuento_activo_prioridad
        ON ventas_packdescuento (activo, prioridad DESC);

        CREATE INDEX idx_pack_descuento_fechas
        ON ventas_packdescuento (fecha_inicio, fecha_fin);

        RAISE NOTICE 'Tabla ventas_packdescuento creada exitosamente';

        -- Insertar pack de ejemplo
        INSERT INTO ventas_packdescuento
        (nombre, descripcion, descuento, servicios_requeridos,
         dias_semana_validos, fecha_inicio, prioridad)
        VALUES
        ('Pack Escapada Semanal',
         'Cabaña + Tinas de domingo a jueves con $45.000 de descuento',
         45000,
         '["ALOJAMIENTO", "TINA"]'::jsonb,
         '[0, 1, 2, 3, 4]'::jsonb,
         CURRENT_DATE,
         10
        );

        RAISE NOTICE 'Pack de ejemplo creado exitosamente';
    ELSE
        RAISE NOTICE 'La tabla ventas_packdescuento ya existe';
    END IF;
END;
$$;

-- Mostrar los packs existentes
SELECT id, nombre, descuento
FROM ventas_packdescuento
ORDER BY prioridad DESC, descuento DESC;