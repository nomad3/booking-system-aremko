#!/usr/bin/env python
import os
import sys

# Aplicar parche de compatibilidad para importlib.metadata ANTES de cualquier importación
# Esto soluciona el error "module 'importlib.metadata' has no attribute 'packages_distributions'"
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

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "No se pudo importar Django. Asegúrate de que está instalado y disponible en tu PYTHONPATH."
        ) from exc
    execute_from_command_line(sys.argv)
