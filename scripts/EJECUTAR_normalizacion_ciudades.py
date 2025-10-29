"""
⚠️  ESTE SCRIPT APLICA CAMBIOS A LA BASE DE DATOS SIN CONFIRMACIÓN INTERACTIVA ⚠️

FASE 3: Normalización de ciudades - EJECUCIÓN DIRECTA

Este script aplica las normalizaciones directamente a la base de datos.
NO requiere confirmación interactiva (para usar con stdin redirect).

IMPORTANTE:
- Este script MODIFICA la base de datos
- Se ejecuta en transacción atómica (todo o nada)
- Si hay errores, revierte automáticamente todos los cambios
- Genera log detallado de todas las operaciones

USO:
    python manage.py shell < scripts/EJECUTAR_normalizacion_ciudades.py

CAMBIOS ESPERADOS (basado en preview):
- ~1,257 clientes normalizados
- 735 → Puerto Montt
- 491 → Puerto Varas
- 5 → Santiago
- Resto → Otras ciudades
"""
import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import transaction
from ventas.models import Cliente
from ventas.data.normalizacion_ciudades import normalizar_ciudad

print("\n" + "="*100)
print("⚠️  NORMALIZACIÓN DE CIUDADES - APLICANDO CAMBIOS A LA BASE DE DATOS")
print("="*100)
print("\nEste script aplicará cambios REALES a la base de datos.")
print("Se ejecuta automáticamente sin confirmación interactiva.")
print("="*100 + "\n")

# ============================================
# 1. ANÁLISIS PREVIO
# ============================================
print("📊 ANÁLISIS PREVIO:")
print("-" * 100)

total_clientes = Cliente.objects.count()
clientes_con_ciudad = Cliente.objects.exclude(ciudad__isnull=True).exclude(ciudad='').count()
clientes_sin_ciudad = total_clientes - clientes_con_ciudad

print(f"Total de clientes:           {total_clientes:>8,}")
print(f"Clientes con ciudad:         {clientes_con_ciudad:>8,}")
print(f"Clientes sin ciudad:         {clientes_sin_ciudad:>8,}")
print()

# ============================================
# 2. OBTENER CLIENTES A NORMALIZAR
# ============================================
print("🔍 ANALIZANDO CLIENTES QUE NECESITAN NORMALIZACIÓN...")
print("-" * 100)

clientes = Cliente.objects.exclude(ciudad__isnull=True).exclude(ciudad='').all()

cambios = []
sin_cambios = 0

for cliente in clientes:
    ciudad_original = cliente.ciudad
    ciudad_normalizada = normalizar_ciudad(ciudad_original)

    if ciudad_original != ciudad_normalizada:
        cambios.append({
            'id': cliente.id,
            'nombre': cliente.nombre,
            'telefono': cliente.telefono,
            'ciudad_original': ciudad_original,
            'ciudad_normalizada': ciudad_normalizada
        })
    else:
        sin_cambios += 1

print(f"✓ Análisis completado:")
print(f"  • Clientes que NECESITAN cambio:  {len(cambios):>6,}")
print(f"  • Clientes SIN cambio necesario:  {sin_cambios:>6,}")
print()

# ============================================
# 3. RESUMEN POR CIUDAD
# ============================================
if cambios:
    print("="*100)
    print("RESUMEN DE NORMALIZACIONES POR CIUDAD")
    print("="*100)

    # Agrupar cambios por ciudad normalizada
    from collections import defaultdict
    cambios_por_ciudad = defaultdict(lambda: {'variantes': defaultdict(int), 'total': 0})

    for cambio in cambios:
        ciudad_norm = cambio['ciudad_normalizada']
        ciudad_orig = cambio['ciudad_original']
        cambios_por_ciudad[ciudad_norm]['variantes'][ciudad_orig] += 1
        cambios_por_ciudad[ciudad_norm]['total'] += 1

    # Ordenar por total de cambios
    ciudades_ordenadas = sorted(cambios_por_ciudad.items(), key=lambda x: x[1]['total'], reverse=True)

    for ciudad_norm, data in ciudades_ordenadas[:15]:
        print(f"\n📍 {ciudad_norm} (Total: {data['total']:,} clientes)")
        for variante, count in sorted(data['variantes'].items(), key=lambda x: x[1], reverse=True)[:5]:
            if variante != ciudad_norm:
                print(f"   • '{variante}' → {count:,} clientes")

    if len(ciudades_ordenadas) > 15:
        print(f"\n... y {len(ciudades_ordenadas) - 15} ciudades más")

    print()

    # ============================================
    # 4. APLICAR CAMBIOS
    # ============================================
    print("="*100)
    print("🔄 APLICANDO CAMBIOS A LA BASE DE DATOS")
    print("="*100)
    print(f"\nSe aplicarán {len(cambios):,} cambios...")
    print()

    actualizados = 0
    errores = []
    inicio = datetime.now()

    try:
        with transaction.atomic():
            for cambio in cambios:
                try:
                    # Usar .update() en lugar de .save() para evitar validaciones del modelo
                    # Esto es importante porque algunos clientes pueden tener teléfonos inválidos
                    # pero solo queremos actualizar el campo ciudad
                    Cliente.objects.filter(id=cambio['id']).update(ciudad=cambio['ciudad_normalizada'])
                    actualizados += 1

                    if actualizados % 100 == 0:
                        print(f"  ✓ {actualizados:,} / {len(cambios):,} clientes actualizados...")

                except Exception as e:
                    errores.append({
                        'cliente_id': cambio['id'],
                        'error': str(e)
                    })

            if errores:
                print(f"\n⚠️  Se encontraron {len(errores)} errores. Revertiendo cambios...")
                raise Exception("Errores durante la actualización")

        fin = datetime.now()
        duracion = (fin - inicio).total_seconds()

        print(f"\n✅ ¡CAMBIOS APLICADOS EXITOSAMENTE!")
        print("="*100)
        print(f"   • Clientes actualizados:     {actualizados:,}")
        print(f"   • Ciudades normalizadas:     {len(set(c['ciudad_normalizada'] for c in cambios))}")
        print(f"   • Tiempo de ejecución:       {duracion:.2f} segundos")
        print()
        print("IMPACTO:")
        print(f"   • Tabla ventas_cliente:      {actualizados:,} registros actualizados")
        print(f"   • Tabla crm_service_history: Afectados automáticamente (usa cliente.ciudad)")
        print()
        print("="*100)

        # ============================================
        # 5. CREAR LOG
        # ============================================
        log_filename = f"normalizacion_ciudades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        try:
            with open(log_filename, 'w', encoding='utf-8') as f:
                f.write("NORMALIZACIÓN DE CIUDADES - LOG DE EJECUCIÓN\n")
                f.write("="*100 + "\n")
                f.write(f"Fecha inicio: {inicio.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Fecha fin:    {fin.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Duración:     {duracion:.2f} segundos\n")
                f.write(f"Total de cambios aplicados: {actualizados:,}\n")
                f.write("\n" + "="*100 + "\n")
                f.write("RESUMEN POR CIUDAD\n")
                f.write("="*100 + "\n\n")

                for ciudad_norm, data in ciudades_ordenadas:
                    f.write(f"\n{ciudad_norm}: {data['total']:,} clientes\n")
                    for variante, count in sorted(data['variantes'].items(), key=lambda x: x[1], reverse=True):
                        if variante != ciudad_norm:
                            f.write(f"  • '{variante}' → {count:,}\n")

                f.write("\n" + "="*100 + "\n")
                f.write("DETALLE DE TODOS LOS CAMBIOS\n")
                f.write("="*100 + "\n\n")

                for cambio in cambios:
                    f.write(f"ID: {cambio['id']}\n")
                    f.write(f"Cliente: {cambio['nombre']}\n")
                    f.write(f"Teléfono: {cambio['telefono']}\n")
                    f.write(f"Cambio: '{cambio['ciudad_original']}' → '{cambio['ciudad_normalizada']}'\n")
                    f.write("-"*100 + "\n")

            print(f"📄 Log detallado guardado en: {log_filename}")
            print()
        except Exception as e:
            print(f"⚠️  No se pudo crear el archivo de log: {e}")
            print("   (Los cambios se aplicaron correctamente)")
            print()

        # ============================================
        # 6. VERIFICACIÓN POST-APLICACIÓN
        # ============================================
        print("="*100)
        print("VERIFICACIÓN POST-APLICACIÓN")
        print("="*100)

        # Contar clientes por las ciudades principales
        puerto_montt_count = Cliente.objects.filter(ciudad='Puerto Montt').count()
        puerto_varas_count = Cliente.objects.filter(ciudad='Puerto Varas').count()
        santiago_count = Cliente.objects.filter(ciudad='Santiago').count()

        print(f"\nCiudades principales (post-normalización):")
        print(f"  • Puerto Montt:  {puerto_montt_count:>6,} clientes")
        print(f"  • Puerto Varas:  {puerto_varas_count:>6,} clientes")
        print(f"  • Santiago:      {santiago_count:>6,} clientes")
        print()

    except Exception as e:
        fin = datetime.now()
        duracion = (fin - inicio).total_seconds()

        print(f"\n❌ ERROR DURANTE LA APLICACIÓN")
        print("="*100)
        print(f"   Error: {e}")
        print(f"   Tiempo transcurrido: {duracion:.2f} segundos")
        print(f"   Clientes procesados antes del error: {actualizados:,}")
        print()
        print("IMPORTANTE:")
        print("   • Todos los cambios fueron revertidos (transacción atómica)")
        print("   • La base de datos NO fue modificada")
        print()

        if errores:
            print("Errores encontrados:")
            for error in errores[:10]:
                print(f"   • Cliente {error['cliente_id']}: {error['error']}")
            if len(errores) > 10:
                print(f"   ... y {len(errores) - 10} errores más")
        print()

else:
    print("="*100)
    print("✅ NO HAY CAMBIOS NECESARIOS")
    print("="*100)
    print("Todas las ciudades ya están normalizadas correctamente.")
    print()

print("="*100)
print("FASE 3 COMPLETADA")
print("="*100 + "\n")
