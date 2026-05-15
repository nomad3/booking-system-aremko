#!/usr/bin/env python
"""
Script para crear las tablas de competidores en la base de datos.
Ejecutar con: python create_competitor_tables.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

sql_commands = """
CREATE TABLE IF NOT EXISTS ventas_competitor (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(200) UNIQUE NOT NULL,
    website VARCHAR(200) NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    facebook_url VARCHAR(200),
    instagram_url VARCHAR(200),
    notas TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ventas_competitorsnapshot (
    id SERIAL PRIMARY KEY,
    competitor_id INTEGER REFERENCES ventas_competitor(id) ON DELETE CASCADE,
    fecha_captura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    precio_entrada_adulto DECIMAL(10,0),
    precio_entrada_nino DECIMAL(10,0),
    tiene_piscinas_termales BOOLEAN DEFAULT FALSE,
    tiene_masajes BOOLEAN DEFAULT FALSE,
    tiene_restaurant BOOLEAN DEFAULT FALSE,
    tiene_alojamiento BOOLEAN DEFAULT FALSE,
    horario_texto VARCHAR(500),
    promociones TEXT,
    meta_description TEXT,
    datos_raw JSONB,
    scraping_exitoso BOOLEAN DEFAULT TRUE,
    error_mensaje TEXT
);

CREATE TABLE IF NOT EXISTS ventas_competitorsocialmedia (
    id SERIAL PRIMARY KEY,
    competitor_id INTEGER REFERENCES ventas_competitor(id) ON DELETE CASCADE,
    fecha_captura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    facebook_seguidores INTEGER,
    facebook_me_gusta INTEGER,
    instagram_seguidores INTEGER,
    instagram_publicaciones_count INTEGER,
    engagement_rate FLOAT,
    posts_ultima_semana INTEGER,
    notas TEXT,
    datos_raw JSONB
);

CREATE INDEX IF NOT EXISTS ventas_comp_competi_10a846_idx
    ON ventas_competitorsnapshot(competitor_id, fecha_captura DESC);

CREATE INDEX IF NOT EXISTS ventas_comp_competi_ff5855_idx
    ON ventas_competitorsocialmedia(competitor_id, fecha_captura DESC);

CREATE INDEX IF NOT EXISTS ventas_competitor_nombre_idx
    ON ventas_competitor(nombre);
"""

print("Creando tablas de competidores...")

with connection.cursor() as cursor:
    cursor.execute(sql_commands)

print("✓ Tablas creadas exitosamente!")
print("✓ ventas_competitor")
print("✓ ventas_competitorsnapshot")
print("✓ ventas_competitorsocialmedia")
print("\nAhora puedes acceder a /admin/ventas/competitor/ para agregar competidores.")
