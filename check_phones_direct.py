"""
Verifica formato de teléfonos conectando directamente a PostgreSQL
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_phones():
    # Conectar a base de datos
    conn = await asyncpg.connect(os.getenv('AREMKO_DATABASE_URL'))

    # Sample de teléfonos
    print('=== SAMPLE DE TELÉFONOS EN LA TABLA CLIENTES ===\n')
    print(f'{'ID':<6} {'NOMBRE':<30} {'TELÉFONO':<20}')
    print('-' * 60)

    rows = await conn.fetch("""
        SELECT id, nombre, telefono
        FROM ventas_cliente
        WHERE telefono IS NOT NULL AND telefono != ''
        LIMIT 20
    """)

    for row in rows:
        print(f'{row["id"]:<6} {row["nombre"][:30]:<30} {row["telefono"]:<20}')

    # Análisis de formato
    print('\n=== ANÁLISIS DE FORMATO ===\n')

    stats = await conn.fetchrow("""
        SELECT
            COUNT(*) FILTER (WHERE telefono LIKE '+%') as with_plus,
            COUNT(*) FILTER (WHERE telefono LIKE '56%' AND telefono NOT LIKE '+%') as with_56,
            COUNT(*) FILTER (WHERE telefono NOT LIKE '56%' AND telefono NOT LIKE '+%') as other,
            COUNT(*) as total
        FROM ventas_cliente
        WHERE telefono IS NOT NULL AND telefono != ''
    """)

    print(f'Con + al inicio: {stats["with_plus"]:,}')
    print(f'Con 56 (sin +): {stats["with_56"]:,}')
    print(f'Otro formato: {stats["other"]:,}')
    print(f'Total: {stats["total"]:,}')

    # Ejemplos de cada formato
    print('\n=== EJEMPLOS POR FORMATO ===\n')

    if stats["with_plus"] > 0:
        ejemplos = await conn.fetch("""
            SELECT telefono FROM ventas_cliente
            WHERE telefono LIKE '+%'
            LIMIT 3
        """)
        print('Con +:', [r['telefono'] for r in ejemplos])

    if stats["with_56"] > 0:
        ejemplos = await conn.fetch("""
            SELECT telefono FROM ventas_cliente
            WHERE telefono LIKE '56%' AND telefono NOT LIKE '+%'
            LIMIT 3
        """)
        print('Con 56:', [r['telefono'] for r in ejemplos])

    if stats["other"] > 0:
        ejemplos = await conn.fetch("""
            SELECT telefono FROM ventas_cliente
            WHERE telefono NOT LIKE '56%' AND telefono NOT LIKE '+%'
            LIMIT 3
        """)
        print('Otro:', [r['telefono'] for r in ejemplos])

    await conn.close()

asyncio.run(check_phones())
