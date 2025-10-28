"""
Script para fusionar clientes históricos a clientes actuales
REGLA: Los clientes actuales (con VentaReserva) son INTOCABLES
Solo se modifican/eliminan clientes que SOLO tienen ServiceHistory
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente, VentaReserva, ServiceHistory
from django.db import transaction
from collections import defaultdict

def classify_clients():
    """
    Clasifica clientes en: ACTUALES (con VentaReserva) vs HISTÓRICOS (solo ServiceHistory)
    """
    print("\n" + "="*80)
    print("📊 CLASIFICANDO CLIENTES")
    print("="*80 + "\n")

    all_clients = Cliente.objects.all()

    current_clients = []  # Tienen VentaReserva (INTOCABLES)
    historical_only = []  # Solo tienen ServiceHistory (MODIFICABLES)
    empty_clients = []    # No tienen nada

    for cliente in all_clients:
        has_ventas = VentaReserva.objects.filter(cliente=cliente).exists()

        try:
            has_historicos = ServiceHistory.objects.filter(cliente=cliente).exists()
        except:
            has_historicos = False

        if has_ventas:
            current_clients.append(cliente)
        elif has_historicos:
            historical_only.append(cliente)
        else:
            empty_clients.append(cliente)

    print(f"✅ Clientes ACTUALES (con VentaReserva): {len(current_clients)}")
    print(f"   → INTOCABLES - Tienen servicios del sistema actual")
    print()
    print(f"📋 Clientes HISTÓRICOS (solo ServiceHistory): {len(historical_only)}")
    print(f"   → MODIFICABLES - Solo tienen servicios importados del CSV")
    print()
    print(f"⚪ Clientes VACÍOS (sin servicios): {len(empty_clients)}")
    print()
    print(f"📊 TOTAL: {len(all_clients)} clientes")
    print()

    return current_clients, historical_only, empty_clients


def find_duplicates_current_vs_historical(current_clients, historical_only):
    """
    Encuentra duplicados entre clientes actuales e históricos
    """
    print("\n" + "="*80)
    print("🔍 BUSCANDO DUPLICADOS: ACTUALES vs HISTÓRICOS")
    print("="*80 + "\n")

    # Crear índice de clientes actuales por teléfono normalizado
    current_by_phone = {}
    for cliente in current_clients:
        if cliente.telefono:
            normalized = cliente.telefono.replace('+', '').strip()
            if normalized:
                if normalized not in current_by_phone:
                    current_by_phone[normalized] = []
                current_by_phone[normalized].append(cliente)

    # Buscar históricos que tienen el mismo teléfono que un actual
    duplicates_to_merge = []  # (cliente_actual, [clientes_historicos])

    for hist_cliente in historical_only:
        if hist_cliente.telefono:
            normalized = hist_cliente.telefono.replace('+', '').strip()
            if normalized and normalized in current_by_phone:
                # Este cliente histórico duplica a uno o más actuales
                for current_cliente in current_by_phone[normalized]:
                    duplicates_to_merge.append((current_cliente, hist_cliente, normalized))

    if not duplicates_to_merge:
        print("✅ No se encontraron duplicados entre clientes actuales e históricos")
        return []

    print(f"⚠️  DUPLICADOS ENCONTRADOS: {len(duplicates_to_merge)} casos")
    print()
    print("Formato: [ACTUAL] ← [HISTÓRICO]")
    print()

    return duplicates_to_merge


def show_merge_plan(duplicates_to_merge, limit=10):
    """
    Muestra el plan de fusión
    """
    print(f"\n{'='*80}")
    print(f"📋 PLAN DE FUSIÓN (primeros {min(limit, len(duplicates_to_merge))} casos)")
    print(f"{'='*80}\n")

    for i, (current, historical, phone) in enumerate(duplicates_to_merge[:limit], 1):
        historicos_count = ServiceHistory.objects.filter(cliente=historical).count()
        ventas_count = VentaReserva.objects.filter(cliente=current).count()

        print(f"{i}. Teléfono: {phone}")
        print(f"   👑 ACTUAL [ID:{current.id}] {current.nombre[:50]}")
        print(f"      └─ Tiene {ventas_count} VentaReservas (INTOCABLE)")
        print()
        print(f"   📋 HISTÓRICO [ID:{historical.id}] {historical.nombre[:50]}")
        print(f"      └─ Tiene {historicos_count} ServiceHistory")
        print(f"      └─ Se moverán al cliente ACTUAL")
        print(f"      └─ Cliente histórico se ELIMINARÁ")
        print()

    if len(duplicates_to_merge) > limit:
        print(f"... y {len(duplicates_to_merge) - limit} casos más\n")


def merge_historical_to_current(duplicates_to_merge, dry_run=True):
    """
    Fusiona clientes históricos hacia clientes actuales
    """
    if dry_run:
        print("\n" + "="*80)
        print("🔄 MODO DRY-RUN: Simulación sin aplicar cambios")
        print("="*80 + "\n")
    else:
        print("\n" + "="*80)
        print("⚠️  MODO REAL: APLICANDO CAMBIOS")
        print("="*80 + "\n")

    merged = 0
    errors = 0

    # Agrupar por cliente actual (puede haber varios históricos para un actual)
    merge_groups = defaultdict(list)
    for current, historical, phone in duplicates_to_merge:
        merge_groups[current.id].append((current, historical, phone))

    for i, (current_id, group) in enumerate(merge_groups.items(), 1):
        current = group[0][0]  # Todos tienen el mismo current
        historicals = [hist for _, hist, _ in group]

        print(f"[{i}/{len(merge_groups)}] Fusionando hacia: [{current.id}] {current.nombre}")

        total_moved = 0
        for historical in historicals:
            historicos_count = ServiceHistory.objects.filter(cliente=historical).count()
            print(f"   ↳ De histórico [{historical.id}] {historical.nombre[:40]}: {historicos_count} servicios")
            total_moved += historicos_count

        if not dry_run:
            try:
                with transaction.atomic():
                    for historical in historicals:
                        # Mover ServiceHistory al cliente actual
                        ServiceHistory.objects.filter(cliente=historical).update(cliente=current)

                        # Eliminar cliente histórico
                        historical.delete()
                        merged += 1

                    print(f"      ✅ Movidos {total_moved} servicios históricos")
            except Exception as e:
                print(f"      ❌ ERROR: {e}")
                errors += 1

        print()

    print("="*80)
    if dry_run:
        print(f"📊 SIMULACIÓN COMPLETADA")
        print(f"   Se fusionarían: {len(duplicates_to_merge)} clientes históricos")
        print(f"   Hacia: {len(merge_groups)} clientes actuales")
        print(f"   Clientes actuales NO se modifican")
    else:
        print(f"✅ FUSIÓN COMPLETADA")
        print(f"   Clientes históricos fusionados: {merged}")
        print(f"   Clientes actuales preservados: {len(merge_groups)}")
        print(f"   Errores: {errors}")
    print("="*80 + "\n")


def normalize_historical_phones():
    """
    Normaliza teléfonos en ServiceHistory (no en Cliente)
    Para que coincidan con el formato de los clientes actuales
    """
    print("\n" + "="*80)
    print("🔧 NORMALIZANDO TELÉFONOS EN SERVICIOS HISTÓRICOS")
    print("="*80 + "\n")

    # Obtener clientes actuales y su formato de teléfono
    current_clients = Cliente.objects.filter(
        id__in=VentaReserva.objects.values_list('cliente_id', flat=True).distinct()
    )

    phone_map = {}  # {normalized: actual_format}
    for cliente in current_clients:
        if cliente.telefono:
            normalized = cliente.telefono.replace('+', '').strip()
            if normalized:
                # Usar el formato del cliente actual como referencia
                phone_map[normalized] = cliente.telefono

    print(f"📞 Clientes actuales como referencia: {len(phone_map)}")
    print(f"   (Estos formatos de teléfono son la VERDAD)")
    print()


def confirm_action():
    """
    Pide confirmación
    """
    print("\n" + "="*80)
    print("⚠️  CONFIRMACIÓN REQUERIDA")
    print("="*80)
    print("\nEsta acción:")
    print("  ✅ NO modificará clientes actuales (con VentaReserva)")
    print("  ✅ Solo moverá ServiceHistory de clientes históricos")
    print("  ✅ Eliminará clientes históricos después de mover sus datos")
    print("  ⚠️  Es IRREVERSIBLE")
    print("\n¿Continuar? (escribe 'SI' para confirmar)")

    response = input("\n> ").strip()
    return response == 'SI'


if __name__ == '__main__':
    import sys

    print("\n" + "="*80)
    print("🔧 FUSIÓN SEGURA: HISTÓRICOS → ACTUALES")
    print("="*80)

    # Paso 1: Clasificar clientes
    current, historical, empty = classify_clients()

    # Paso 2: Encontrar duplicados
    duplicates = find_duplicates_current_vs_historical(current, historical)

    if not duplicates:
        print("\n✅ No hay duplicados para fusionar")
        sys.exit(0)

    # Paso 3: Mostrar plan
    show_merge_plan(duplicates, limit=15)

    # Paso 4: Simular
    print("\n" + "="*80)
    print("PASO 1: SIMULACIÓN (DRY-RUN)")
    print("="*80)
    merge_historical_to_current(duplicates, dry_run=True)

    # Paso 5: Aplicar si se solicita
    if '--apply' in sys.argv:
        if confirm_action():
            print("\n🚀 Aplicando cambios...\n")
            merge_historical_to_current(duplicates, dry_run=False)
            print("\n✅ PROCESO COMPLETADO")
            print("\n💡 Los clientes actuales NO fueron modificados")
            print("   Solo se movieron datos históricos y se eliminaron duplicados históricos")
        else:
            print("\n❌ Operación cancelada")
    else:
        print("\n💡 PARA APLICAR LOS CAMBIOS:")
        print("   python merge_historical_to_current.py --apply")
        print()
