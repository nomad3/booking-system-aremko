#!/usr/bin/env python
"""
Script para crear tabla PackDescuento en producción
Ejecutar con: python create_pack_table_prod.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

def main():
    with connection.cursor() as cursor:
        # Check if table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'ventas_packdescuento'
            );
        """)

        if cursor.fetchone()[0]:
            print("✅ La tabla ventas_packdescuento ya existe")
        else:
            print("📦 Creando tabla ventas_packdescuento...")

            # Create table
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

            # Create indexes
            cursor.execute("""
                CREATE INDEX idx_pack_descuento_activo_prioridad
                ON ventas_packdescuento (activo, prioridad DESC);
            """)

            cursor.execute("""
                CREATE INDEX idx_pack_descuento_fechas
                ON ventas_packdescuento (fecha_inicio, fecha_fin);
            """)

            print("✅ Tabla creada con éxito")

            # Insert example pack
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

            print("✅ Pack de ejemplo creado")

    # Show existing packs
    print("\n📋 Packs existentes:")
    from ventas.models import PackDescuento
    for pack in PackDescuento.objects.all():
        print(f"  - {pack.nombre}: ${pack.descuento:,.0f} descuento")

if __name__ == "__main__":
    main()