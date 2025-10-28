"""
Script para investigar y resolver duplicados de clientes específicos
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente, VentaReserva, ServiceHistory
from django.db import transaction

def investigate_phone_duplicates(phone_without_plus):
    """
    Investiga duplicados para un número específico
    """
    # Buscar ambas variantes
    phone_with_plus = f'+{phone_without_plus}'

    print(f"\n{'='*80}")
    print(f"🔍 INVESTIGANDO TELÉFONO: {phone_without_plus}")
    print(f"{'='*80}\n")

    # Buscar clientes con ambos formatos
    clientes_sin_plus = Cliente.objects.filter(telefono=phone_without_plus)
    clientes_con_plus = Cliente.objects.filter(telefono=phone_with_plus)

    todos_clientes = list(clientes_sin_plus) + list(clientes_con_plus)

    if len(todos_clientes) == 0:
        print("❌ No se encontraron clientes con este teléfono")
        return

    if len(todos_clientes) == 1:
        print(f"✅ Solo hay 1 cliente con este teléfono (sin duplicados)")
        c = todos_clientes[0]
        print(f"   ID: {c.id} | Nombre: {c.nombre} | Tel: {c.telefono}")
        return

    print(f"⚠️  DUPLICADOS ENCONTRADOS: {len(todos_clientes)} clientes\n")

    # Mostrar detalles de cada cliente
    for i, cliente in enumerate(todos_clientes, 1):
        print(f"CLIENTE {i}:")
        print(f"  ID: {cliente.id}")
        print(f"  Nombre: {cliente.nombre}")
        print(f"  Teléfono: {cliente.telefono}")
        print(f"  Email: {cliente.email or 'N/A'}")
        print(f"  Ciudad: {cliente.ciudad or 'N/A'}")
        print(f"  País: {cliente.pais or 'N/A'}")
        print(f"  Creado: {cliente.created_at}")

        # Contar servicios
        ventas = VentaReserva.objects.filter(cliente=cliente).count()
        try:
            historicos = ServiceHistory.objects.filter(cliente=cliente).count()
        except:
            historicos = 0

        print(f"  VentaReserva: {ventas}")
        print(f"  ServiceHistory: {historicos}")
        print(f"  Total Servicios: {ventas + historicos}")
        print()

    # Test de normalización
    print("🧪 TEST DE NORMALIZACIÓN:")
    normalized_with = Cliente.normalize_phone(phone_with_plus)
    normalized_without = Cliente.normalize_phone(phone_without_plus)
    print(f"  '{phone_with_plus}' → '{normalized_with}'")
    print(f"  '{phone_without_plus}' → '{normalized_without}'")
    print()

    # Determinar cliente principal (más antiguo)
    cliente_principal = min(todos_clientes, key=lambda c: c.created_at if c.created_at else c.id)
    clientes_duplicados = [c for c in todos_clientes if c.id != cliente_principal.id]

    print(f"📌 CLIENTE PRINCIPAL (más antiguo):")
    print(f"   ID: {cliente_principal.id} | {cliente_principal.nombre}")
    print()

    print(f"🗑️  CLIENTES A FUSIONAR:")
    for c in clientes_duplicados:
        print(f"   ID: {c.id} | {c.nombre}")
    print()

    return cliente_principal, clientes_duplicados


def merge_clients(cliente_principal, clientes_duplicados, dry_run=True):
    """
    Fusiona clientes duplicados en el principal
    """
    if dry_run:
        print("🔄 MODO DRY-RUN: Mostrando qué se haría sin aplicar cambios\n")
    else:
        print("⚠️  MODO REAL: Aplicando cambios...\n")

    for cliente_dup in clientes_duplicados:
        print(f"Fusionando cliente {cliente_dup.id} ({cliente_dup.nombre}) → {cliente_principal.id} ({cliente_principal.nombre})")

        # Contar qué se moverá
        ventas_count = VentaReserva.objects.filter(cliente=cliente_dup).count()
        try:
            historicos_count = ServiceHistory.objects.filter(cliente=cliente_dup).count()
        except:
            historicos_count = 0

        print(f"  → Mover {ventas_count} VentaReserva")
        print(f"  → Mover {historicos_count} ServiceHistory")

        if not dry_run:
            with transaction.atomic():
                # Mover VentaReserva
                VentaReserva.objects.filter(cliente=cliente_dup).update(cliente=cliente_principal)

                # Mover ServiceHistory
                try:
                    ServiceHistory.objects.filter(cliente=cliente_dup).update(cliente=cliente_principal)
                except:
                    pass

                # Actualizar datos del principal si están vacíos
                updated = False
                if not cliente_principal.email and cliente_dup.email:
                    cliente_principal.email = cliente_dup.email
                    updated = True

                if not cliente_principal.ciudad and cliente_dup.ciudad:
                    cliente_principal.ciudad = cliente_dup.ciudad
                    updated = True

                if not cliente_principal.pais and cliente_dup.pais:
                    cliente_principal.pais = cliente_dup.pais
                    updated = True

                if updated:
                    Cliente.objects.filter(id=cliente_principal.id).update(
                        email=cliente_principal.email,
                        ciudad=cliente_principal.ciudad,
                        pais=cliente_principal.pais
                    )

                # Normalizar teléfono del principal
                normalized = Cliente.normalize_phone(cliente_principal.telefono)
                if normalized and normalized != cliente_principal.telefono:
                    print(f"  → Normalizar teléfono: {cliente_principal.telefono} → {normalized}")
                    Cliente.objects.filter(id=cliente_principal.id).update(telefono=normalized)

                # Eliminar duplicado
                cliente_dup.delete()
                print(f"  ✅ Cliente {cliente_dup.id} eliminado")

        print()


if __name__ == '__main__':
    print("\n" + "="*80)
    print("🔍 INVESTIGADOR DE DUPLICADOS - AREMKO")
    print("="*80)

    # Caso 1: 56975544661
    print("\n\n📞 CASO 1: 56975544661")
    result1 = investigate_phone_duplicates('56975544661')

    if result1:
        principal1, duplicados1 = result1
        print("\n💡 ¿FUSIONAR ESTOS CLIENTES?")
        merge_clients(principal1, duplicados1, dry_run=True)

    # Caso 2: 56962801057
    print("\n\n" + "="*80)
    print("\n📞 CASO 2: 56962801057")
    result2 = investigate_phone_duplicates('56962801057')

    if result2:
        principal2, duplicados2 = result2
        print("\n💡 ¿FUSIONAR ESTOS CLIENTES?")
        merge_clients(principal2, duplicados2, dry_run=True)

    print("\n" + "="*80)
    print("✅ ANÁLISIS COMPLETADO")
    print("="*80)
    print("\n💡 PARA APLICAR LOS CAMBIOS:")
    print("   1. Revisa el análisis anterior")
    print("   2. Si estás de acuerdo, edita el script y cambia dry_run=False")
    print("   3. Ejecuta nuevamente: python investigate_duplicates.py")
    print()
