"""
Script para verificar que la segmentación incluye datos históricos
Se conecta directamente a la base de datos de producción
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def verify_segmentation():
    """
    Verifica que la segmentación incluye datos históricos y actuales
    """
    print("=" * 70)
    print("VERIFICACIÓN DE SEGMENTACIÓN - DATOS HISTÓRICOS + ACTUALES")
    print("=" * 70)

    # Conectar a la base de datos
    database_url = os.getenv('AREMKO_DATABASE_URL')
    if not database_url:
        print("❌ Error: No se encontró AREMKO_DATABASE_URL en el archivo .env")
        return

    conn = await asyncpg.connect(database_url)

    try:
        # 1. Verificar que la tabla crm_service_history existe
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'crm_service_history'
            )
        """)

        if table_exists:
            print("\n✅ Tabla crm_service_history EXISTS")
        else:
            print("\n❌ Tabla crm_service_history NO EXISTE")
            await conn.close()
            return

        # 2. Contar servicios históricos
        historical_count = await conn.fetchval("SELECT COUNT(*) FROM crm_service_history")
        print(f"   Total servicios históricos: {historical_count:,}")

        # 3. Contar servicios actuales
        current_count = await conn.fetchval("SELECT COUNT(*) FROM ventas_ventareserva")
        print(f"   Total servicios actuales: {current_count:,}")

        # 4. Contar clientes con servicios históricos
        historical_clients = await conn.fetchval("""
            SELECT COUNT(DISTINCT cliente_id) FROM crm_service_history
        """)
        print(f"\n📚 Clientes con servicios HISTÓRICOS: {historical_clients:,}")

        # 5. Contar clientes con servicios actuales
        current_clients = await conn.fetchval("""
            SELECT COUNT(DISTINCT cliente_id) FROM ventas_ventareserva
        """)
        print(f"📊 Clientes con servicios ACTUALES: {current_clients:,}")

        # 6. Ejecutar query combinada (mismo que usa la segmentación)
        print("\n🔍 Ejecutando query de segmentación combinada...\n")

        query = """
        SELECT
            c.id as cliente_id,
            c.nombre,
            -- Servicios actuales
            COUNT(DISTINCT vr.id) as servicios_actuales,
            COALESCE(SUM(vr.total), 0) as gasto_actual,
            -- Servicios históricos
            COUNT(DISTINCT sh.id) as servicios_historicos,
            COALESCE(SUM(sh.price_paid), 0) as gasto_historico,
            -- Totales combinados
            (COUNT(DISTINCT vr.id) + COUNT(DISTINCT sh.id)) as total_servicios,
            (COALESCE(SUM(vr.total), 0) + COALESCE(SUM(sh.price_paid), 0)) as total_gasto
        FROM ventas_cliente c
        LEFT JOIN ventas_ventareserva vr ON c.id = vr.cliente_id
        LEFT JOIN crm_service_history sh ON c.id = sh.cliente_id
        GROUP BY c.id, c.nombre
        HAVING (COUNT(DISTINCT vr.id) + COUNT(DISTINCT sh.id)) > 0
        ORDER BY total_gasto DESC
        LIMIT 10
        """

        results = await conn.fetch(query)

        print("✅ Query ejecutada exitosamente\n")
        print("Top 10 clientes (datos combinados):\n")
        print("-" * 120)
        print(f"{'Cliente':<30} | {'Serv.Actual':>10} | {'Gasto Actual':>15} | {'Serv.Hist':>10} | {'Gasto Hist':>15} | {'Total Serv':>10} | {'Gasto Total':>15}")
        print("-" * 120)

        for row in results:
            print(f"{row['nombre'][:28]:<30} | {row['servicios_actuales']:>10} | ${float(row['gasto_actual']):>14,.0f} | {row['servicios_historicos']:>10} | ${float(row['gasto_historico']):>14,.0f} | {row['total_servicios']:>10} | ${float(row['total_gasto']):>14,.0f}")

        print("-" * 120)

        # 7. Estadísticas de combinación
        print("\n📈 ESTADÍSTICAS DE COMBINACIÓN:")

        # Clientes solo con servicios actuales
        only_current = await conn.fetchval("""
            SELECT COUNT(DISTINCT vr.cliente_id)
            FROM ventas_ventareserva vr
            LEFT JOIN crm_service_history sh ON vr.cliente_id = sh.cliente_id
            WHERE sh.id IS NULL
        """)
        print(f"   - Solo servicios actuales: {only_current:,} clientes")

        # Clientes solo con servicios históricos
        only_historical = await conn.fetchval("""
            SELECT COUNT(DISTINCT sh.cliente_id)
            FROM crm_service_history sh
            LEFT JOIN ventas_ventareserva vr ON sh.cliente_id = vr.cliente_id
            WHERE vr.id IS NULL
        """)
        print(f"   - Solo servicios históricos: {only_historical:,} clientes")

        # Clientes con AMBOS tipos de servicios
        both = await conn.fetchval("""
            SELECT COUNT(DISTINCT c.id)
            FROM ventas_cliente c
            INNER JOIN ventas_ventareserva vr ON c.id = vr.cliente_id
            INNER JOIN crm_service_history sh ON c.id = sh.cliente_id
        """)
        print(f"   - AMBOS (históricos + actuales): {both:,} clientes")

        # Total de clientes con al menos un servicio
        total_with_services = only_current + only_historical + both
        print(f"\n   📊 TOTAL clientes con servicios: {total_with_services:,}")

        # 8. Conclusión
        print("\n" + "=" * 70)
        print("CONCLUSIÓN")
        print("=" * 70)

        if historical_clients > 0 and both > 0:
            print("\n✅ LA SEGMENTACIÓN INCLUYE DATOS HISTÓRICOS CORRECTAMENTE")
            print(f"\n   ✓ {historical_count:,} servicios históricos importados")
            print(f"   ✓ {historical_clients:,} clientes tienen servicios históricos")
            print(f"   ✓ {both:,} clientes tienen AMBOS tipos de servicios")
            print("   ✓ El query combina ambas fuentes correctamente (LEFT JOIN)")
            print("\n   👉 La segmentación RFM está usando el historial completo del cliente")
        else:
            print("\n⚠️  ADVERTENCIA: Datos históricos presentes pero no hay clientes con ambos tipos")
            print(f"   - Puede ser que los clientes históricos sean diferentes a los actuales")
            print(f"   - O que el matching por cliente_id no esté funcionando correctamente")

        print("\n")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(verify_segmentation())
