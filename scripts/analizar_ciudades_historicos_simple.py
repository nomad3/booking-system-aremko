"""
FASE 1.1: Análisis de ciudades en datos históricos (ServiceHistory)
Versión simplificada usando asyncpg directo a PostgreSQL

NO MODIFICA DATOS - Solo lectura y análisis
"""
import asyncio
import asyncpg
import os
from collections import Counter, defaultdict
from dotenv import load_dotenv

load_dotenv()

async def main():
    # Conectar a la base de datos
    db_url = os.getenv('AREMKO_DATABASE_URL') or os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ Error: DATABASE_URL no configurado")
        return

    print("\n" + "="*100)
    print("ANÁLISIS DE CIUDADES EN DATOS HISTÓRICOS (crm_service_history)")
    print("="*100 + "\n")

    try:
        conn = await asyncpg.connect(db_url)

        # Total de registros
        total_registros = await conn.fetchval("SELECT COUNT(*) FROM crm_service_history")
        print(f"✓ Total de registros históricos: {total_registros:,}\n")

        # Obtener todas las ciudades
        ciudades = await conn.fetch("SELECT city FROM crm_service_history")
        lista_ciudades = [row['city'] for row in ciudades]

        # Contar ciudades
        contador_ciudades = Counter(lista_ciudades)

        # Filtrar valores vacíos
        ciudades_con_valor = {ciudad: count for ciudad, count in contador_ciudades.items()
                              if ciudad and ciudad.strip()}
        ciudades_vacias = contador_ciudades.get('') + contador_ciudades.get(None, 0)

        print("="*100)
        print("RESUMEN GENERAL")
        print("="*100)
        print(f"Ciudades únicas (con valor):     {len(ciudades_con_valor):>6,}")
        print(f"Registros sin ciudad:            {ciudades_vacias:>6,}")
        print(f"Total de registros:              {total_registros:>6,}")
        print()

        # Ordenar por cantidad
        ciudades_ordenadas = sorted(ciudades_con_valor.items(), key=lambda x: x[1], reverse=True)

        print("="*100)
        print("TOP 30 CIUDADES MÁS FRECUENTES")
        print("="*100)
        print(f"{'#':<4} {'CIUDAD':<50} {'REGISTROS':>12} {'%':>8}")
        print("-"*100)

        for i, (ciudad, count) in enumerate(ciudades_ordenadas[:30], 1):
            porcentaje = (count / total_registros) * 100
            print(f"{i:<4} {ciudad:<50} {count:>12,} {porcentaje:>7.2f}%")

        # Agrupar variantes similares
        print("\n" + "="*100)
        print("DETECCIÓN DE VARIANTES (posibles duplicados)")
        print("="*100)

        grupos = defaultdict(list)
        for ciudad, count in ciudades_con_valor.items():
            ciudad_norm = ciudad.lower().strip()
            ciudad_norm = ciudad_norm.replace('.', '').replace(',', '')
            ciudad_norm = ciudad_norm.replace('á', 'a').replace('é', 'e').replace('í', 'i')
            ciudad_norm = ciudad_norm.replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')
            grupos[ciudad_norm].append((ciudad, count))

        variantes_detectadas = {norm: variantes for norm, variantes in grupos.items() if len(variantes) > 1}

        if variantes_detectadas:
            print("\nSe detectaron variantes para las siguientes ciudades:\n")
            for norm_ciudad, variantes in sorted(variantes_detectadas.items(),
                                                 key=lambda x: sum(v[1] for v in x[1]),
                                                 reverse=True)[:15]:
                total_grupo = sum(count for _, count in variantes)
                print(f"\n📍 '{norm_ciudad}' - Total: {total_grupo:,} registros")
                for ciudad_original, count in sorted(variantes, key=lambda x: x[1], reverse=True):
                    print(f"      • '{ciudad_original}': {count:,}")

        await conn.close()

        print("\n" + "="*100)
        print("ANÁLISIS COMPLETADO")
        print("="*100 + "\n")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
