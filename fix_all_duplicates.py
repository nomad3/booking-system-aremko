"""
Script para encontrar y fusionar TODOS los duplicados de teléfonos (+56 vs 56)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente, VentaReserva, ServiceHistory
from django.db import transaction
from collections import defaultdict

def find_all_duplicates():
    """
    Encuentra TODOS los pares de duplicados (+56 vs 56)
    """
    print("\n" + "="*80)
    print("🔍 BUSCANDO TODOS LOS DUPLICADOS DE TELÉFONOS")
    print("="*80 + "\n")

    # Obtener todos los clientes
    all_clients = Cliente.objects.all().order_by('id')

    # Agrupar por teléfono normalizado (sin +)
    phone_groups = defaultdict(list)

    for cliente in all_clients:
        if cliente.telefono:
            # Normalizar quitando el +
            normalized = cliente.telefono.replace('+', '').strip()
            if normalized:
                phone_groups[normalized].append(cliente)

    # Encontrar grupos con duplicados
    duplicates = []
    for normalized_phone, clients in phone_groups.items():
        if len(clients) > 1:
            duplicates.append((normalized_phone, clients))

    if not duplicates:
        print("✅ No se encontraron duplicados")
        return []

    print(f"⚠️  DUPLICADOS ENCONTRADOS: {len(duplicates)} grupos\n")

    # Mostrar resumen
    total_clients_affected = sum(len(clients) for _, clients in duplicates)
    total_to_merge = total_clients_affected - len(duplicates)  # Restar los principales

    print(f"📊 RESUMEN:")
    print(f"   Total grupos duplicados: {len(duplicates)}")
    print(f"   Total clientes afectados: {total_clients_affected}")
    print(f"   Clientes a fusionar/eliminar: {total_to_merge}")
    print()

    return duplicates


def show_duplicate_details(duplicates, limit=10):
    """
    Muestra detalles de los primeros N duplicados
    """
    print(f"\n{'='*80}")
    print(f"📋 PRIMEROS {min(limit, len(duplicates))} DUPLICADOS ENCONTRADOS")
    print(f"{'='*80}\n")

    for i, (normalized_phone, clients) in enumerate(duplicates[:limit], 1):
        print(f"GRUPO {i}: Teléfono normalizado {normalized_phone}")
        print(f"   Clientes duplicados: {len(clients)}")

        for j, cliente in enumerate(clients, 1):
            ventas = VentaReserva.objects.filter(cliente=cliente).count()
            try:
                historicos = ServiceHistory.objects.filter(cliente=cliente).count()
            except:
                historicos = 0

            marker = "👑" if j == 1 else "  "
            print(f"   {marker} [{cliente.id:4d}] {cliente.nombre[:40]:<40} | Tel: {cliente.telefono:<15} | Servicios: {ventas + historicos:3d}")

        print()

    if len(duplicates) > limit:
        print(f"... y {len(duplicates) - limit} grupos más\n")


def merge_all_duplicates(duplicates, dry_run=True):
    """
    Fusiona todos los duplicados encontrados
    """
    if dry_run:
        print("\n" + "="*80)
        print("🔄 MODO DRY-RUN: Simulación sin aplicar cambios")
        print("="*80 + "\n")
    else:
        print("\n" + "="*80)
        print("⚠️  MODO REAL: APLICANDO CAMBIOS PERMANENTES")
        print("="*80 + "\n")

    total_merged = 0
    total_errors = 0

    for i, (normalized_phone, clients) in enumerate(duplicates, 1):
        # Ordenar por created_at (más antiguo primero) o por ID si no hay created_at
        clients_sorted = sorted(clients, key=lambda c: (c.created_at or c.id, c.id))

        principal = clients_sorted[0]
        duplicados = clients_sorted[1:]

        print(f"[{i}/{len(duplicates)}] Fusionando {normalized_phone}")
        print(f"   👑 Principal: [{principal.id}] {principal.nombre}")

        for dup in duplicados:
            print(f"      ↳ Fusionar: [{dup.id}] {dup.nombre}")

        if not dry_run:
            try:
                with transaction.atomic():
                    for dup in duplicados:
                        # Mover VentaReserva
                        ventas_moved = VentaReserva.objects.filter(cliente=dup).update(cliente=principal)

                        # Mover ServiceHistory
                        historicos_moved = 0
                        try:
                            historicos_moved = ServiceHistory.objects.filter(cliente=dup).update(cliente=principal)
                        except:
                            pass

                        # Actualizar datos del principal si están vacíos
                        if not principal.email and dup.email:
                            principal.email = dup.email
                        if not principal.ciudad and dup.ciudad:
                            principal.ciudad = dup.ciudad
                        if not principal.pais and dup.pais:
                            principal.pais = dup.pais

                        # Eliminar duplicado
                        dup.delete()
                        total_merged += 1

                        print(f"         ✅ Movidos: {ventas_moved} ventas, {historicos_moved} históricos")

                    # Guardar cambios del principal y normalizar teléfono
                    Cliente.objects.filter(id=principal.id).update(
                        email=principal.email,
                        ciudad=principal.ciudad,
                        pais=principal.pais,
                        telefono=normalized_phone  # Normalizar sin +
                    )

            except Exception as e:
                print(f"         ❌ ERROR: {e}")
                total_errors += 1

        print()

    print("="*80)
    if dry_run:
        print(f"📊 SIMULACIÓN COMPLETADA")
        print(f"   Se fusionarían: {sum(len(clients)-1 for _, clients in duplicates)} clientes")
        print(f"   En {len(duplicates)} grupos")
    else:
        print(f"✅ FUSIÓN COMPLETADA")
        print(f"   Clientes fusionados: {total_merged}")
        print(f"   Errores: {total_errors}")
    print("="*80 + "\n")


def confirm_action():
    """
    Pide confirmación para aplicar cambios
    """
    print("\n" + "="*80)
    print("⚠️  ADVERTENCIA: ACCIÓN IRREVERSIBLE")
    print("="*80)
    print("\nEstás a punto de FUSIONAR y ELIMINAR clientes duplicados.")
    print("Esta acción NO se puede deshacer.")
    print("\n¿Estás seguro de continuar? (escribe 'SI' para confirmar)")

    response = input("\n> ").strip()
    return response == 'SI'


if __name__ == '__main__':
    import sys

    print("\n" + "="*80)
    print("🔧 REPARADOR DE DUPLICADOS - AREMKO")
    print("="*80)

    # Paso 1: Encontrar duplicados
    duplicates = find_all_duplicates()

    if not duplicates:
        print("\n✅ No hay duplicados para fusionar")
        sys.exit(0)

    # Paso 2: Mostrar detalles
    show_duplicate_details(duplicates, limit=10)

    # Paso 3: Simular fusión
    print("\n" + "="*80)
    print("PASO 1: SIMULACIÓN (DRY-RUN)")
    print("="*80)
    merge_all_duplicates(duplicates, dry_run=True)

    # Paso 4: Preguntar si aplicar cambios
    if '--apply' in sys.argv:
        if confirm_action():
            print("\n🚀 Aplicando cambios...\n")
            merge_all_duplicates(duplicates, dry_run=False)
            print("\n✅ PROCESO COMPLETADO")
        else:
            print("\n❌ Operación cancelada")
    else:
        print("\n💡 PARA APLICAR LOS CAMBIOS:")
        print("   python fix_all_duplicates.py --apply")
        print()
