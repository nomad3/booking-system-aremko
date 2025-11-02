#!/usr/bin/env python3
"""
Script para limpiar (DELETE) todos los registros de crm_service_history
PRECAUCIÓN: Este script BORRA PERMANENTEMENTE todos los servicios históricos
Solo ejecutar después de confirmar que existe un backup válido
"""
import psycopg2
import os
import sys
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL no encontrada")
    sys.exit(1)

def limpiar_servicios():
    print("=" * 70)
    print("⚠️  LIMPIEZA DE SERVICIOS HISTÓRICOS")
    print("=" * 70)
    print()
    print("⚠️  ADVERTENCIA: Este script BORRARÁ PERMANENTEMENTE todos los")
    print("   registros de la tabla crm_service_history")
    print()
    print("✅ Requisito: Debe existir un backup válido antes de proceder")
    print()

    # Conectar
    print("🔌 Conectando a PostgreSQL...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    conn.autocommit = False  # Transacción manual

    # Contar registros actuales
    cur.execute("SELECT COUNT(*) FROM crm_service_history")
    count_antes = cur.fetchone()[0]
    print(f"📊 Registros actuales en crm_service_history: {count_antes:,}")
    print()

    if count_antes == 0:
        print("ℹ️  La tabla ya está vacía, no hay nada que borrar")
        cur.close()
        conn.close()
        return

    # Confirmación
    print("=" * 70)
    print("⚠️  CONFIRMACIÓN REQUERIDA")
    print("=" * 70)
    print(f"Se borrarán {count_antes:,} registros de servicios históricos")
    print()
    respuesta = input("¿Deseas continuar? (escribe 'CONFIRMAR' para proceder): ")

    if respuesta.strip().upper() != 'CONFIRMAR':
        print()
        print("❌ Operación cancelada por el usuario")
        cur.close()
        conn.close()
        return

    print()
    print("🗑️  Borrando registros...")

    try:
        # DELETE
        cur.execute("DELETE FROM crm_service_history")
        registros_borrados = cur.rowcount

        # COMMIT
        conn.commit()

        print()
        print("=" * 70)
        print("✅ LIMPIEZA COMPLETADA")
        print("=" * 70)
        print(f"Registros borrados: {registros_borrados:,}")

        # Verificar que esté vacía
        cur.execute("SELECT COUNT(*) FROM crm_service_history")
        count_despues = cur.fetchone()[0]
        print(f"Registros restantes: {count_despues:,}")

        if count_despues == 0:
            print()
            print("✅ La tabla crm_service_history está ahora vacía")
            print("   Lista para importar nuevos datos limpios")
        else:
            print()
            print("⚠️  ADVERTENCIA: La tabla no está completamente vacía")

    except Exception as e:
        conn.rollback()
        print()
        print(f"❌ ERROR durante limpieza: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 70)

    cur.close()
    conn.close()

if __name__ == '__main__':
    try:
        limpiar_servicios()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operación interrumpida por el usuario")
    except Exception as e:
        print(f"\n❌ ERROR FATAL: {e}")
        import traceback
        traceback.print_exc()
