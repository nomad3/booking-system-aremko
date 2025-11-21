#!/usr/bin/env python
"""
Script para crear la tabla ventas_giftcardexperiencia directamente con SQL.

Este script ejecuta el SQL de la migración 0061 sin usar el comando migrate,
evitando problemas con el estado de Django.

Uso:
    python crear_tabla_giftcard_experiencia.py
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

def crear_tabla():
    """Crea la tabla ventas_giftcardexperiencia directamente con SQL"""

    print("=" * 70)
    print("🔧 Creación de Tabla GiftCardExperiencia")
    print("=" * 70)
    print()

    # SQL para crear la tabla
    sql_create_table = """
    CREATE TABLE IF NOT EXISTS ventas_giftcardexperiencia (
        id BIGSERIAL PRIMARY KEY,
        id_experiencia VARCHAR(50) UNIQUE NOT NULL,
        categoria VARCHAR(20) NOT NULL,
        nombre VARCHAR(200) NOT NULL,
        descripcion VARCHAR(500) NOT NULL,
        descripcion_giftcard TEXT NOT NULL,
        imagen VARCHAR(100) NOT NULL,
        monto_fijo INTEGER NULL,
        montos_sugeridos JSONB DEFAULT '[]'::jsonb,
        activo BOOLEAN DEFAULT TRUE NOT NULL,
        orden INTEGER DEFAULT 0 NOT NULL,
        creado TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
        modificado TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
    );
    """

    sql_create_indexes = """
    CREATE INDEX IF NOT EXISTS ventas_gift_categor_idx
    ON ventas_giftcardexperiencia (categoria, activo);

    CREATE INDEX IF NOT EXISTS ventas_gift_activo_idx
    ON ventas_giftcardexperiencia (activo, orden);
    """

    try:
        with connection.cursor() as cursor:
            print("📝 Verificando si la tabla ya existe...")
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_tables
                    WHERE schemaname = 'public'
                    AND tablename = 'ventas_giftcardexperiencia'
                );
            """)

            existe = cursor.fetchone()[0]

            if existe:
                print("⚠️  La tabla ventas_giftcardexperiencia ya existe.")
                print("   No es necesario crearla.")
                return

            print("🚀 Creando tabla ventas_giftcardexperiencia...")
            cursor.execute(sql_create_table)
            print("✅ Tabla creada exitosamente")

            print("📊 Creando índices...")
            cursor.execute(sql_create_indexes)
            print("✅ Índices creados exitosamente")

        print("\n" + "=" * 70)
        print("🎉 ¡Tabla creada exitosamente!")
        print("=" * 70)
        print()
        print("🎯 Ahora puedes poblar las experiencias:")
        print("   python poblar_experiencias_giftcard.py")
        print()

    except Exception as e:
        print(f"\n❌ Error al crear la tabla: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    crear_tabla()
