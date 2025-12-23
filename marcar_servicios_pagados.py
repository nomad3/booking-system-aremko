#!/usr/bin/env python
"""
Script para marcar todos los servicios como pagados hasta el 23 de diciembre de 2025.
Esto refleja la realidad actual - todos los masajistas han sido pagados hasta esta fecha.
Ejecutar desde el shell de Render.
"""
import os
import sys
from datetime import date

# Aplicar parche de compatibilidad para importlib.metadata ANTES de cualquier importación
if sys.version_info < (3, 10):
    try:
        import importlib.metadata as metadata
        if not hasattr(metadata, 'packages_distributions'):
            def packages_distributions():
                """Implementación compatible para Python < 3.10"""
                pkg_to_dist = {}
                for dist in metadata.distributions():
                    if dist.files:
                        for file in dist.files:
                            if file.suffix == ".py" and "/" in str(file):
                                parts = str(file).split("/")
                                pkg = parts[0]
                                if pkg not in pkg_to_dist:
                                    pkg_to_dist[pkg] = []
                                if dist.metadata["Name"] not in pkg_to_dist[pkg]:
                                    pkg_to_dist[pkg].append(dist.metadata["Name"])
                return pkg_to_dist
            metadata.packages_distributions = packages_distributions
    except Exception:
        pass

import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

def main():
    from ventas.models import ReservaServicio, Proveedor
    from django.db.models import Count

    print("=" * 60)
    print("MARCANDO SERVICIOS COMO PAGADOS HASTA EL 23/12/2025")
    print("=" * 60)
    print()

    # Fecha límite: 23 de diciembre de 2025
    fecha_limite = date(2025, 12, 23)

    print(f"Fecha límite establecida: {fecha_limite.strftime('%d/%m/%Y')}")
    print()

    # Buscar servicios pendientes de pago hasta esa fecha
    servicios_pendientes = ReservaServicio.objects.filter(
        fecha_agendamiento__lte=fecha_limite,
        venta_reserva__estado_pago='pagado',
        proveedor_asignado__isnull=False,
        proveedor_asignado__es_masajista=True,
        pagado_a_proveedor=False
    ).select_related('proveedor_asignado', 'servicio', 'venta_reserva__cliente')

    total_servicios = servicios_pendientes.count()

    if total_servicios == 0:
        print("✅ No hay servicios pendientes de marcar como pagados.")
        print("   Todos los servicios ya están marcados correctamente.")
        return True

    print(f"Se encontraron {total_servicios} servicios pendientes de marcar como pagados.")
    print()

    # Agrupar por masajista para mostrar resumen
    servicios_por_masajista = {}
    for servicio in servicios_pendientes:
        masajista = servicio.proveedor_asignado
        if masajista not in servicios_por_masajista:
            servicios_por_masajista[masajista] = []
        servicios_por_masajista[masajista].append(servicio)

    print("Resumen por masajista:")
    print("-" * 40)
    for masajista, servicios in servicios_por_masajista.items():
        print(f"  {masajista.nombre}: {len(servicios)} servicios")
    print()

    # Confirmar antes de proceder
    print("=" * 60)
    print("⚠️  IMPORTANTE: Esta acción marcará todos estos servicios")
    print("   como PAGADOS hasta el 23/12/2025")
    print("=" * 60)
    print()
    print("Presione ENTER para continuar o Ctrl+C para cancelar...")

    try:
        input()
    except KeyboardInterrupt:
        print("\n❌ Operación cancelada por el usuario")
        return False

    print()
    print("Marcando servicios como pagados...")

    # Actualizar todos los servicios
    try:
        servicios_actualizados = servicios_pendientes.update(
            pagado_a_proveedor=True
        )

        print(f"✅ {servicios_actualizados} servicios marcados como pagados exitosamente")

    except Exception as e:
        print(f"❌ Error al actualizar servicios: {e}")
        return False

    print()
    print("=" * 60)
    print("VERIFICACIÓN FINAL")
    print("=" * 60)
    print()

    # Verificar el estado actual
    servicios_pendientes_ahora = ReservaServicio.objects.filter(
        fecha_agendamiento__lte=fecha_limite,
        venta_reserva__estado_pago='pagado',
        proveedor_asignado__isnull=False,
        proveedor_asignado__es_masajista=True,
        pagado_a_proveedor=False
    ).count()

    servicios_pagados_total = ReservaServicio.objects.filter(
        fecha_agendamiento__lte=fecha_limite,
        venta_reserva__estado_pago='pagado',
        proveedor_asignado__isnull=False,
        proveedor_asignado__es_masajista=True,
        pagado_a_proveedor=True
    ).count()

    print(f"Servicios pendientes de pago (hasta 23/12/2025): {servicios_pendientes_ahora}")
    print(f"Servicios marcados como pagados (hasta 23/12/2025): {servicios_pagados_total}")

    # Mostrar servicios futuros que sí quedan pendientes
    servicios_futuros = ReservaServicio.objects.filter(
        fecha_agendamiento__gt=fecha_limite,
        venta_reserva__estado_pago='pagado',
        proveedor_asignado__isnull=False,
        proveedor_asignado__es_masajista=True,
        pagado_a_proveedor=False
    ).count()

    if servicios_futuros > 0:
        print(f"\n📅 Servicios posteriores al 23/12/2025 pendientes de pago: {servicios_futuros}")
        print("   (Estos servicios NO fueron marcados como pagados)")

    print()
    print("=" * 60)
    print("✅ PROCESO COMPLETADO EXITOSAMENTE")
    print("=" * 60)
    print()
    print("Todos los servicios hasta el 23/12/2025 han sido marcados como pagados.")
    print("El sistema de pagos está listo para gestionar servicios futuros.")

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)