#!/usr/bin/env python
"""
Script de diagnóstico para problemas de rendimiento en clientes
"""
import os
import sys
import django
import time
from django.db import connection
from django.db.models import Count, Avg, Max, Q

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko.settings')
django.setup()

from ventas.models import Cliente, VentaReserva

def analizar_rendimiento_clientes():
    print("=== DIAGNÓSTICO DE RENDIMIENTO - CLIENTES ===\n")

    # 1. Estadísticas básicas
    print("1. ESTADÍSTICAS BÁSICAS:")
    total_clientes = Cliente.objects.count()
    print(f"   - Total clientes: {total_clientes:,}")

    clientes_con_email = Cliente.objects.filter(email__isnull=False).exclude(email='').count()
    print(f"   - Clientes con email: {clientes_con_email:,}")

    clientes_con_ventas = Cliente.objects.annotate(
        num_ventas=Count('ventareserva')
    ).filter(num_ventas__gt=0).count()
    print(f"   - Clientes con ventas: {clientes_con_ventas:,}")

    # 2. Análisis de duplicados potenciales
    print("\n2. ANÁLISIS DE DUPLICADOS:")

    # Teléfonos duplicados (no debería haber por unique=True)
    from django.db.models import Count
    duplicados_telefono = Cliente.objects.values('telefono').annotate(
        count=Count('id')
    ).filter(count__gt=1).count()
    print(f"   - Teléfonos duplicados: {duplicados_telefono}")

    # Nombres similares
    nombres_similares = Cliente.objects.values('nombre').annotate(
        count=Count('id')
    ).filter(count__gt=1).order_by('-count')[:5]
    print("   - Top 5 nombres repetidos:")
    for item in nombres_similares:
        print(f"     * {item['nombre']}: {item['count']} veces")

    # 3. Análisis de índices
    print("\n3. ANÁLISIS DE ÍNDICES:")
    with connection.cursor() as cursor:
        # Ver índices de la tabla Cliente
        cursor.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'ventas_cliente'
            ORDER BY indexname;
        """)
        indices = cursor.fetchall()
        print("   Índices actuales:")
        for idx in indices:
            print(f"   - {idx[0]}")

    # 4. Pruebas de rendimiento
    print("\n4. PRUEBAS DE RENDIMIENTO:")

    # Búsqueda por nombre
    start = time.time()
    Cliente.objects.filter(nombre__icontains='maria').count()
    tiempo_nombre = time.time() - start
    print(f"   - Búsqueda por nombre (ILIKE): {tiempo_nombre:.3f}s")

    # Búsqueda por teléfono
    start = time.time()
    Cliente.objects.filter(telefono__contains='9').count()
    tiempo_telefono = time.time() - start
    print(f"   - Búsqueda por teléfono (LIKE): {tiempo_telefono:.3f}s")

    # Búsqueda combinada (como en admin)
    start = time.time()
    Cliente.objects.filter(
        Q(nombre__icontains='a') |
        Q(telefono__icontains='9') |
        Q(email__icontains='@')
    )[:50].count()
    tiempo_combinado = time.time() - start
    print(f"   - Búsqueda combinada (admin): {tiempo_combinado:.3f}s")

    # 5. Análisis de propiedades calculadas
    print("\n5. ANÁLISIS DE PROPIEDADES CALCULADAS:")

    # Tiempo para calcular gasto_total de un cliente
    cliente_test = Cliente.objects.filter(
        ventareserva__isnull=False
    ).first()

    if cliente_test:
        start = time.time()
        gasto = cliente_test.gasto_total()
        tiempo_gasto = time.time() - start
        print(f"   - Cálculo gasto_total(): {tiempo_gasto:.3f}s")

        start = time.time()
        visitas = cliente_test.numero_visitas()
        tiempo_visitas = time.time() - start
        print(f"   - Cálculo numero_visitas(): {tiempo_visitas:.3f}s")

    # 6. Análisis de queries N+1
    print("\n6. ANÁLISIS DE PROBLEMAS N+1:")

    # Reset queries
    from django.db import reset_queries
    reset_queries()

    # Simular carga de lista de clientes (como en admin)
    start = time.time()
    clientes = list(Cliente.objects.all()[:10])
    for cliente in clientes:
        _ = str(cliente)  # Esto ejecuta __str__

    queries_count = len(connection.queries)
    tiempo_lista = time.time() - start

    print(f"   - Cargar 10 clientes: {tiempo_lista:.3f}s")
    print(f"   - Queries ejecutadas: {queries_count}")

    # 7. Análisis de normalización de teléfonos
    print("\n7. ANÁLISIS DE NORMALIZACIÓN DE TELÉFONOS:")

    # Contar teléfonos con diferentes formatos
    telefonos_con_espacios = Cliente.objects.filter(telefono__contains=' ').count()
    telefonos_con_guiones = Cliente.objects.filter(telefono__contains='-').count()
    telefonos_con_mas = Cliente.objects.filter(telefono__startswith='+').count()

    print(f"   - Con espacios: {telefonos_con_espacios}")
    print(f"   - Con guiones: {telefonos_con_guiones}")
    print(f"   - Con +: {telefonos_con_mas}")

    # 8. Sugerencias
    print("\n8. SUGERENCIAS DE OPTIMIZACIÓN:")

    if tiempo_nombre > 0.1:
        print("   ⚠️  La búsqueda por nombre es lenta. Considerar:")
        print("      - Índice GIN con pg_trgm para búsquedas ILIKE")
        print("      - Índice funcional lower(nombre)")

    if tiempo_combinado > 0.2:
        print("   ⚠️  La búsqueda combinada es lenta. Considerar:")
        print("      - Índices compuestos")
        print("      - Búsqueda full-text con PostgreSQL")

    if queries_count > 15:
        print("   ⚠️  Posible problema N+1. Considerar:")
        print("      - Usar select_related/prefetch_related")
        print("      - Revisar propiedades calculadas")

    print("\n=== FIN DEL DIAGNÓSTICO ===")

if __name__ == "__main__":
    analizar_rendimiento_clientes()