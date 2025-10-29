"""
Verifica clientes duplicados por teléfono (con y sin +)
"""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

# Conectar a base de datos
DATABASE_URL = os.getenv('AREMKO_DATABASE_URL')
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Buscar el teléfono específico mostrado en la screenshot
phone_without_plus = '56975544661'
phone_with_plus = '+56975544661'

print('=== BÚSQUEDA DE CLIENTES CON TELÉFONO 56975544661 ===\n')

# Buscar ambas variantes
cur.execute("""
    SELECT id, nombre, email, telefono, ciudad, pais, created_at
    FROM ventas_cliente
    WHERE telefono IN (%s, %s)
    ORDER BY telefono, id
""", (phone_without_plus, phone_with_plus))

rows = cur.fetchall()

if rows:
    print(f'Se encontraron {len(rows)} cliente(s) con este teléfono:\n')
    for row in rows:
        print(f'ID: {row[0]}')
        print(f'Nombre: {row[1]}')
        print(f'Email: {row[2]}')
        print(f'Teléfono: {row[3]}')
        print(f'Ciudad: {row[4]}')
        print(f'País: {row[5]}')
        print(f'Creado: {row[6]}')
        print('-' * 60)
else:
    print('No se encontraron clientes con este teléfono.')

# Buscar TODOS los duplicados por teléfono (diferentes formatos)
print('\n=== ANÁLISIS GENERAL DE DUPLICADOS POR FORMATO DE TELÉFONO ===\n')

# Primero, normalizar todos los teléfonos para encontrar duplicados
cur.execute("""
    SELECT
        REPLACE(telefono, '+', '') as phone_normalized,
        COUNT(*) as count,
        STRING_AGG(DISTINCT telefono, ', ') as formats
    FROM ventas_cliente
    WHERE telefono IS NOT NULL AND telefono != ''
    GROUP BY REPLACE(telefono, '+', '')
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    LIMIT 20
""")

duplicates = cur.fetchall()

if duplicates:
    print(f'Se encontraron {len(duplicates)} números con formatos duplicados:\n')
    print(f'{'TELÉFONO NORMALIZADO':<20} {'CANTIDAD':<10} {'FORMATOS EXISTENTES':<40}')
    print('=' * 80)
    for dup in duplicates:
        print(f'{dup[0]:<20} {dup[1]:<10} {dup[2]:<40}')
else:
    print('No se encontraron duplicados por formato de teléfono.')

cur.close()
conn.close()
