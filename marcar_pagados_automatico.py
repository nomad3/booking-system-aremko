#!/usr/bin/env python
"""
Script automático para marcar todos los servicios como pagados hasta el 23 de diciembre de 2025.
Versión sin confirmación manual - para ejecución directa.
"""
import os
import sys
from datetime import date

# Aplicar parche de compatibilidad para importlib.metadata
if sys.version_info < (3, 10):
    try:
        import importlib.metadata as metadata
        if not hasattr(metadata, 'packages_distributions'):
            def packages_distributions():
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
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import ReservaServicio

# Fecha límite: 23 de diciembre de 2025
fecha_limite = date(2025, 12, 23)

print(f"Marcando todos los servicios como pagados hasta el {fecha_limite.strftime('%d/%m/%Y')}...")

# Actualizar todos los servicios de una vez
servicios_actualizados = ReservaServicio.objects.filter(
    fecha_agendamiento__lte=fecha_limite,
    venta_reserva__estado_pago='pagado',
    proveedor_asignado__isnull=False,
    proveedor_asignado__es_masajista=True,
    pagado_a_proveedor=False
).update(pagado_a_proveedor=True)

print(f"✅ {servicios_actualizados} servicios marcados como pagados")

# Mostrar estadísticas finales
pendientes_futuros = ReservaServicio.objects.filter(
    fecha_agendamiento__gt=fecha_limite,
    venta_reserva__estado_pago='pagado',
    proveedor_asignado__isnull=False,
    proveedor_asignado__es_masajista=True,
    pagado_a_proveedor=False
).count()

if pendientes_futuros > 0:
    print(f"📅 Quedan {pendientes_futuros} servicios futuros (después del 23/12/2025) pendientes de pago")

print("✅ Proceso completado")