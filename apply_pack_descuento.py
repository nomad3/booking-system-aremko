#!/usr/bin/env python
"""
Script para crear la tabla PackDescuento directamente en la base de datos
Ya que las migraciones están deshabilitadas
"""
import os
import sys
import django

# Añadir el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection
from django.core.management import execute_from_command_line

def create_pack_descuento_table():
    """Crear la tabla PackDescuento directamente"""

    with connection.cursor() as cursor:
        # Verificar si la tabla ya existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'ventas_packdescuento'
            );
        """)

        if cursor.fetchone()[0]:
            print("✅ La tabla 'ventas_packdescuento' ya existe")
            return

        # Crear la tabla
        cursor.execute("""
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
        """)

        # Crear índices
        cursor.execute("""
            CREATE INDEX idx_pack_descuento_activo_prioridad
            ON ventas_packdescuento (activo, prioridad DESC);
        """)

        cursor.execute("""
            CREATE INDEX idx_pack_descuento_fechas
            ON ventas_packdescuento (fecha_inicio, fecha_fin);
        """)

        print("✅ Tabla 'ventas_packdescuento' creada exitosamente")

        # Insertar pack de ejemplo
        cursor.execute("""
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
        """)

        print("✅ Pack de ejemplo 'Pack Escapada Semanal' creado")

if __name__ == "__main__":
    try:
        create_pack_descuento_table()
        print("\n🎉 Script completado exitosamente")

        # Mostrar los packs creados
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, nombre, descuento FROM ventas_packdescuento")
            packs = cursor.fetchall()

            print("\nPacks de descuento en la base de datos:")
            for pack in packs:
                print(f"  - ID: {pack[0]}, Nombre: {pack[1]}, Descuento: ${pack[2]:,.0f}")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)