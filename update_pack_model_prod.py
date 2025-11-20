#!/usr/bin/env python
"""
Script para actualizar el modelo PackDescuento en producción
con soporte para servicios específicos
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
        print("🔄 Actualizando modelo PackDescuento...")

        # 1. Agregar campo usa_servicios_especificos
        try:
            cursor.execute("""
                ALTER TABLE ventas_packdescuento
                ADD COLUMN usa_servicios_especificos BOOLEAN NOT NULL DEFAULT false;
            """)
            print("✅ Campo usa_servicios_especificos agregado")
        except Exception as e:
            if 'already exists' in str(e):
                print("ℹ️ Campo usa_servicios_especificos ya existe")
            else:
                print(f"❌ Error agregando campo: {e}")
                raise

        # 2. Crear tabla intermedia para ManyToMany
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'ventas_packdescuento_servicios_especificos'
            );
        """)

        if not cursor.fetchone()[0]:
            cursor.execute("""
                CREATE TABLE ventas_packdescuento_servicios_especificos (
                    id SERIAL PRIMARY KEY,
                    packdescuento_id INTEGER NOT NULL REFERENCES ventas_packdescuento(id) ON DELETE CASCADE,
                    servicio_id INTEGER NOT NULL REFERENCES ventas_servicio(id) ON DELETE CASCADE,
                    UNIQUE(packdescuento_id, servicio_id)
                );
            """)

            # Crear índices
            cursor.execute("""
                CREATE INDEX idx_pack_servicio_pack
                ON ventas_packdescuento_servicios_especificos(packdescuento_id);
            """)

            cursor.execute("""
                CREATE INDEX idx_pack_servicio_servicio
                ON ventas_packdescuento_servicios_especificos(servicio_id);
            """)

            print("✅ Tabla de relación ManyToMany creada")
        else:
            print("ℹ️ Tabla de relación ManyToMany ya existe")

        # 3. Hacer servicios_requeridos nullable
        try:
            cursor.execute("""
                ALTER TABLE ventas_packdescuento
                ALTER COLUMN servicios_requeridos DROP NOT NULL;
            """)
            print("✅ Campo servicios_requeridos ahora es nullable")
        except Exception as e:
            print(f"ℹ️ Campo ya era nullable o error: {e}")

    print("\n✅ Actualización completada exitosamente")
    print("\nAhora puedes crear packs con servicios específicos:")
    print("- Pack con Cabaña Torre + Tina Puyehue")
    print("- Pack con servicios específicos de tu elección")

if __name__ == "__main__":
    main()