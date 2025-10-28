"""
Script para normalizar TODOS los teléfonos en la base de datos actual
Convierte +56XXXXXXXXX → 56XXXXXXXXX
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente
from django.db import transaction

def normalize_all_phones(dry_run=True):
    """
    Normaliza todos los teléfonos en la base de datos
    Quita el signo + de todos los teléfonos
    """
    if dry_run:
        print("\n" + "="*80)
        print("🔄 MODO DRY-RUN: Simulación sin aplicar cambios")
        print("="*80 + "\n")
    else:
        print("\n" + "="*80)
        print("⚠️  MODO REAL: APLICANDO CAMBIOS")
        print("="*80 + "\n")

    all_clients = Cliente.objects.all()
    total = all_clients.count()

    normalized_count = 0
    no_change_count = 0
    errors = []

    print(f"📊 Total clientes en base de datos: {total}\n")
    print("Procesando...\n")

    for i, cliente in enumerate(all_clients, 1):
        if i % 100 == 0:
            print(f"   Procesados: {i}/{total}")

        if not cliente.telefono:
            no_change_count += 1
            continue

        # Verificar si tiene el signo +
        if cliente.telefono.startswith('+'):
            old_phone = cliente.telefono
            new_phone = cliente.telefono.replace('+', '').strip()

            if dry_run:
                print(f"   [{cliente.id}] {old_phone} → {new_phone}")
                normalized_count += 1
            else:
                try:
                    # Actualizar directamente en la BD sin usar save()
                    # para evitar validaciones y triggers
                    Cliente.objects.filter(id=cliente.id).update(telefono=new_phone)
                    normalized_count += 1
                except Exception as e:
                    errors.append({
                        'id': cliente.id,
                        'nombre': cliente.nombre,
                        'telefono': old_phone,
                        'error': str(e)
                    })
        else:
            no_change_count += 1

    print("\n" + "="*80)
    if dry_run:
        print("📊 SIMULACIÓN COMPLETADA")
        print(f"   Se normalizarían: {normalized_count} teléfonos")
        print(f"   Sin cambios: {no_change_count}")
    else:
        print("✅ NORMALIZACIÓN COMPLETADA")
        print(f"   Teléfonos normalizados: {normalized_count}")
        print(f"   Sin cambios: {no_change_count}")
        print(f"   Errores: {len(errors)}")

        if errors:
            print("\n⚠️  ERRORES ENCONTRADOS:")
            for err in errors[:10]:
                print(f"   [{err['id']}] {err['nombre']} ({err['telefono']}): {err['error']}")
            if len(errors) > 10:
                print(f"   ... y {len(errors) - 10} errores más")

    print("="*80 + "\n")

    return {
        'total': total,
        'normalized': normalized_count,
        'no_change': no_change_count,
        'errors': errors
    }


def verify_no_duplicates_after():
    """
    Verifica que no haya duplicados después de la normalización
    """
    print("\n" + "="*80)
    print("🔍 VERIFICANDO DUPLICADOS POST-NORMALIZACIÓN")
    print("="*80 + "\n")

    from collections import defaultdict

    all_clients = Cliente.objects.all()
    phone_groups = defaultdict(list)

    for cliente in all_clients:
        if cliente.telefono:
            phone_groups[cliente.telefono].append(cliente)

    duplicates = [(phone, clients) for phone, clients in phone_groups.items() if len(clients) > 1]

    if not duplicates:
        print("✅ NO HAY DUPLICADOS DE TELÉFONO")
        print("   Todos los teléfonos son únicos\n")
        return True
    else:
        print(f"⚠️  SE ENCONTRARON {len(duplicates)} GRUPOS DUPLICADOS:\n")
        for phone, clients in duplicates[:10]:
            print(f"   📞 {phone}: {len(clients)} clientes")
            for c in clients:
                print(f"      [{c.id}] {c.nombre}")

        if len(duplicates) > 10:
            print(f"\n   ... y {len(duplicates) - 10} grupos más")

        print()
        return False


if __name__ == '__main__':
    import sys

    print("\n" + "="*80)
    print("🔧 NORMALIZADOR DE TELÉFONOS - AREMKO")
    print("="*80)
    print("\nEste script normaliza TODOS los teléfonos en la base de datos")
    print("Convierte: +56XXXXXXXXX → 56XXXXXXXXX")
    print("Afecta a TODOS los clientes (actuales e históricos)")
    print()

    # Paso 1: Simular
    print("PASO 1: SIMULACIÓN")
    print("-" * 80)
    result = normalize_all_phones(dry_run=True)

    # Paso 2: Aplicar si se solicita
    if '--apply' in sys.argv:
        print("\n⚠️  ¿Aplicar la normalización? (escribe 'SI' para confirmar)")
        response = input("\n> ").strip()

        if response == 'SI':
            print("\n🚀 Aplicando normalización...\n")
            result = normalize_all_phones(dry_run=False)

            print("\n✅ PROCESO COMPLETADO")
            print(f"\nResumen:")
            print(f"   Total clientes: {result['total']}")
            print(f"   Normalizados: {result['normalized']}")
            print(f"   Sin cambios: {result['no_change']}")
            print(f"   Errores: {len(result['errors'])}")

            # Verificar duplicados
            verify_no_duplicates_after()
        else:
            print("\n❌ Operación cancelada")
    else:
        print("\n💡 PARA APLICAR LA NORMALIZACIÓN:")
        print("   python normalize_all_phones.py --apply")
        print()
