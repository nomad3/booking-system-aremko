"""
Script para analizar duplicados restantes después de la primera fusión
Identifica POR QUÉ no se fusionaron y propone soluciones
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente, VentaReserva, ServiceHistory
from django.db import transaction
from collections import defaultdict

def find_all_remaining_duplicates():
    """
    Encuentra TODOS los duplicados que aún existen
    """
    print("\n" + "="*80)
    print("🔍 ANALIZANDO DUPLICADOS RESTANTES")
    print("="*80 + "\n")

    all_clients = Cliente.objects.all()
    phone_groups = defaultdict(list)

    # Agrupar por teléfono normalizado
    for cliente in all_clients:
        if cliente.telefono:
            normalized = cliente.telefono.replace('+', '').strip()
            if normalized:
                phone_groups[normalized].append(cliente)

    # Encontrar grupos con duplicados
    duplicates = []
    for normalized_phone, clients in phone_groups.items():
        if len(clients) > 1:
            duplicates.append((normalized_phone, clients))

    if not duplicates:
        print("✅ NO HAY DUPLICADOS")
        return []

    print(f"⚠️  DUPLICADOS ENCONTRADOS: {len(duplicates)} grupos\n")
    return duplicates


def analyze_duplicate_group(phone, clients):
    """
    Analiza UN grupo de duplicados y determina por qué no se fusionó
    """
    print(f"📞 TELÉFONO: {phone}")
    print(f"   Clientes duplicados: {len(clients)}\n")

    # Clasificar cada cliente
    clients_info = []
    for cliente in clients:
        ventas = VentaReserva.objects.filter(cliente=cliente).count()
        try:
            historicos = ServiceHistory.objects.filter(cliente=cliente).count()
        except:
            historicos = 0

        tipo = 'ACTUAL' if ventas > 0 else ('HISTÓRICO' if historicos > 0 else 'VACÍO')

        clients_info.append({
            'cliente': cliente,
            'ventas': ventas,
            'historicos': historicos,
            'tipo': tipo,
            'total_servicios': ventas + historicos
        })

        print(f"   [{cliente.id}] {cliente.nombre[:45]:<45}")
        print(f"      Teléfono en DB: {cliente.telefono}")
        print(f"      Tipo: {tipo}")
        print(f"      Ventas: {ventas}, Históricos: {historicos}, Total: {ventas + historicos}")
        print()

    # Determinar por qué NO se fusionó
    actuales = [c for c in clients_info if c['tipo'] == 'ACTUAL']
    historicos = [c for c in clients_info if c['tipo'] == 'HISTÓRICO']
    vacios = [c for c in clients_info if c['tipo'] == 'VACÍO']

    print(f"   📊 RESUMEN:")
    print(f"      ACTUALES: {len(actuales)}")
    print(f"      HISTÓRICOS: {len(historicos)}")
    print(f"      VACÍOS: {len(vacios)}")
    print()

    # Diagnosticar problema
    if len(actuales) >= 2:
        print(f"   ⚠️  PROBLEMA: Hay {len(actuales)} clientes ACTUALES con el mismo teléfono")
        print(f"      → Estos NO se fusionan automáticamente porque ambos tienen VentaReserva")
        print(f"      → REQUIERE decisión manual: ¿cuál es el principal?")
        return {
            'phone': phone,
            'clients': clients_info,
            'problem': 'multiple_actuals',
            'requires_manual': True
        }

    elif len(actuales) == 1 and len(historicos) >= 1:
        print(f"   ⚠️  PROBLEMA: Hay 1 ACTUAL y {len(historicos)} HISTÓRICOS")
        print(f"      → DEBIÓ fusionarse automáticamente")
        print(f"      → Verificar si los teléfonos tienen formato ligeramente diferente")
        return {
            'phone': phone,
            'clients': clients_info,
            'problem': 'should_have_merged',
            'requires_manual': False,
            'can_auto_fix': True
        }

    elif len(historicos) >= 2:
        print(f"   ℹ️  CASO: Solo hay {len(historicos)} clientes HISTÓRICOS")
        print(f"      → No tienen VentaReserva, se pueden fusionar entre sí")
        return {
            'phone': phone,
            'clients': clients_info,
            'problem': 'multiple_historicals',
            'requires_manual': False,
            'can_auto_fix': True
        }

    elif len(vacios) >= 1:
        print(f"   ℹ️  CASO: Hay {len(vacios)} clientes VACÍOS")
        print(f"      → Se pueden eliminar sin problema")
        return {
            'phone': phone,
            'clients': clients_info,
            'problem': 'empty_clients',
            'requires_manual': False,
            'can_auto_fix': True
        }

    print()


def analyze_all_duplicates():
    """
    Analiza todos los duplicados restantes
    """
    duplicates = find_all_remaining_duplicates()

    if not duplicates:
        return []

    print("\n" + "="*80)
    print("📋 ANÁLISIS DETALLADO DE CADA GRUPO")
    print("="*80 + "\n")

    analysis_results = []
    for i, (phone, clients) in enumerate(duplicates, 1):
        print(f"GRUPO {i}/{len(duplicates)}:")
        print("-" * 80)
        result = analyze_duplicate_group(phone, clients)
        analysis_results.append(result)
        print("=" * 80)
        print()

    return analysis_results


def summarize_problems(analysis_results):
    """
    Resume los problemas encontrados
    """
    print("\n" + "="*80)
    print("📊 RESUMEN DE PROBLEMAS")
    print("="*80 + "\n")

    problems = defaultdict(list)
    for result in analysis_results:
        if result:
            problems[result['problem']].append(result)

    total_manual = sum(1 for r in analysis_results if r and r.get('requires_manual'))
    total_auto = sum(1 for r in analysis_results if r and r.get('can_auto_fix'))

    print(f"Total grupos duplicados: {len(analysis_results)}")
    print(f"   Requieren decisión MANUAL: {total_manual}")
    print(f"   Se pueden auto-corregir: {total_auto}")
    print()

    if 'multiple_actuals' in problems:
        cases = problems['multiple_actuals']
        print(f"⚠️  MÚLTIPLES ACTUALES: {len(cases)} casos")
        print(f"   → Hay 2+ clientes con VentaReserva y mismo teléfono")
        print(f"   → REQUIERE DECISIÓN MANUAL")
        for case in cases:
            print(f"      {case['phone']}: {len(case['clients'])} clientes")
        print()

    if 'should_have_merged' in problems:
        cases = problems['should_have_merged']
        print(f"🔧 DEBIERON FUSIONARSE: {len(cases)} casos")
        print(f"   → Hay 1 ACTUAL + HISTÓRICOS que no se fusionaron")
        print(f"   → Se puede auto-corregir")
        for case in cases:
            print(f"      {case['phone']}")
        print()

    if 'multiple_historicals' in problems:
        cases = problems['multiple_historicals']
        print(f"📋 HISTÓRICOS MÚLTIPLES: {len(cases)} casos")
        print(f"   → Solo hay clientes históricos (sin VentaReserva)")
        print(f"   → Se pueden fusionar entre sí")
        for case in cases:
            print(f"      {case['phone']}")
        print()

    if 'empty_clients' in problems:
        cases = problems['empty_clients']
        print(f"⚪ CLIENTES VACÍOS: {len(cases)} casos")
        print(f"   → Se pueden eliminar")
        for case in cases:
            print(f"      {case['phone']}")
        print()

    return problems


def propose_fixes(problems):
    """
    Propone soluciones automáticas
    """
    print("\n" + "="*80)
    print("💡 SOLUCIONES PROPUESTAS")
    print("="*80 + "\n")

    auto_fixable = []

    # 1. Casos que debieron fusionarse
    if 'should_have_merged' in problems:
        cases = problems['should_have_merged']
        print(f"1️⃣  FUSIONAR ACTUALES + HISTÓRICOS ({len(cases)} casos):")
        for case in cases:
            actual = [c for c in case['clients'] if c['tipo'] == 'ACTUAL'][0]
            historicos = [c for c in case['clients'] if c['tipo'] == 'HISTÓRICO']
            print(f"   📞 {case['phone']}")
            print(f"      Mantener: [{actual['cliente'].id}] {actual['cliente'].nombre}")
            print(f"      Fusionar: {len(historicos)} histórico(s)")
            auto_fixable.append({
                'type': 'merge_to_actual',
                'principal': actual,
                'duplicates': historicos
            })
        print()

    # 2. Fusionar históricos entre sí
    if 'multiple_historicals' in problems:
        cases = problems['multiple_historicals']
        print(f"2️⃣  FUSIONAR HISTÓRICOS ENTRE SÍ ({len(cases)} casos):")
        for case in cases:
            sorted_hist = sorted(case['clients'],
                               key=lambda c: (c['cliente'].created_at or c['cliente'].id))
            principal = sorted_hist[0]
            duplicates = sorted_hist[1:]
            print(f"   📞 {case['phone']}")
            print(f"      Mantener: [{principal['cliente'].id}] {principal['cliente'].nombre}")
            print(f"      Fusionar: {len(duplicates)} histórico(s)")
            auto_fixable.append({
                'type': 'merge_historicals',
                'principal': principal,
                'duplicates': duplicates
            })
        print()

    # 3. Eliminar vacíos
    if 'empty_clients' in problems:
        cases = problems['empty_clients']
        print(f"3️⃣  ELIMINAR CLIENTES VACÍOS ({len(cases)} casos):")
        for case in cases:
            vacios = [c for c in case['clients'] if c['tipo'] == 'VACÍO']
            print(f"   📞 {case['phone']}: {len(vacios)} vacío(s)")
            for vacio in vacios:
                auto_fixable.append({
                    'type': 'delete_empty',
                    'client': vacio
                })
        print()

    # 4. Casos manuales
    if 'multiple_actuals' in problems:
        cases = problems['multiple_actuals']
        print(f"⚠️  REQUIEREN DECISIÓN MANUAL ({len(cases)} casos):")
        print(f"   Estos tienen múltiples clientes ACTUALES con VentaReserva")
        print(f"   NO se auto-corrigen - requiere revisar manualmente")
        for case in cases:
            print(f"   📞 {case['phone']}: {len([c for c in case['clients'] if c['tipo'] == 'ACTUAL'])} actuales")
        print()

    return auto_fixable


def apply_auto_fixes(auto_fixable, dry_run=True):
    """
    Aplica las correcciones automáticas
    """
    if dry_run:
        print("\n" + "="*80)
        print("🔄 MODO DRY-RUN: Simulación")
        print("="*80 + "\n")
    else:
        print("\n" + "="*80)
        print("⚠️  APLICANDO CORRECCIONES")
        print("="*80 + "\n")

    merged = 0
    deleted = 0
    errors = 0

    for i, fix in enumerate(auto_fixable, 1):
        try:
            if fix['type'] in ['merge_to_actual', 'merge_historicals']:
                principal = fix['principal']['cliente']
                duplicates = [d['cliente'] for d in fix['duplicates']]

                print(f"[{i}/{len(auto_fixable)}] Fusionando hacia [{principal.id}] {principal.nombre}")

                if not dry_run:
                    with transaction.atomic():
                        for dup in duplicates:
                            # Mover datos
                            VentaReserva.objects.filter(cliente=dup).update(cliente=principal)
                            ServiceHistory.objects.filter(cliente=dup).update(cliente=principal)

                            # Eliminar duplicado
                            dup.delete()
                            merged += 1

                print(f"   ✅ Fusionados {len(duplicates)} cliente(s)")

            elif fix['type'] == 'delete_empty':
                cliente = fix['client']['cliente']
                print(f"[{i}/{len(auto_fixable)}] Eliminando vacío [{cliente.id}] {cliente.nombre}")

                if not dry_run:
                    with transaction.atomic():
                        cliente.delete()
                        deleted += 1

                print(f"   ✅ Eliminado")

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            errors += 1

        print()

    print("="*80)
    if dry_run:
        print(f"📊 SIMULACIÓN COMPLETADA")
        print(f"   Se fusionarían: {len([f for f in auto_fixable if f['type'] in ['merge_to_actual', 'merge_historicals']])} grupos")
        print(f"   Se eliminarían: {len([f for f in auto_fixable if f['type'] == 'delete_empty'])} vacíos")
    else:
        print(f"✅ CORRECCIONES APLICADAS")
        print(f"   Clientes fusionados: {merged}")
        print(f"   Clientes eliminados: {deleted}")
        print(f"   Errores: {errors}")
    print("="*80 + "\n")


if __name__ == '__main__':
    import sys

    print("\n" + "="*80)
    print("🔧 ANALIZADOR DE DUPLICADOS RESTANTES - AREMKO")
    print("="*80)

    # Paso 1: Analizar todos los duplicados
    analysis_results = analyze_all_duplicates()

    if not analysis_results:
        print("\n✅ No hay duplicados para analizar")
        sys.exit(0)

    # Paso 2: Resumir problemas
    problems = summarize_problems(analysis_results)

    # Paso 3: Proponer soluciones
    auto_fixable = propose_fixes(problems)

    if not auto_fixable:
        print("\n✅ No hay correcciones automáticas disponibles")
        print("   Todos los casos requieren decisión manual")
        sys.exit(0)

    # Paso 4: Simular correcciones
    print("\n" + "="*80)
    print("SIMULACIÓN DE CORRECCIONES AUTOMÁTICAS")
    print("="*80)
    apply_auto_fixes(auto_fixable, dry_run=True)

    # Paso 5: Aplicar si se solicita
    if '--apply' in sys.argv:
        print("\n⚠️  ¿Aplicar estas correcciones? (escribe 'SI' para confirmar)")
        response = input("\n> ").strip()
        if response == 'SI':
            print("\n🚀 Aplicando correcciones...\n")
            apply_auto_fixes(auto_fixable, dry_run=False)
            print("\n✅ PROCESO COMPLETADO")
        else:
            print("\n❌ Operación cancelada")
    else:
        print("\n💡 PARA APLICAR LAS CORRECCIONES:")
        print("   python analyze_remaining_duplicates.py --apply")
        print()
