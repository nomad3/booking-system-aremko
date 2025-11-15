import os

# Aplicar parche de compatibilidad para importlib.metadata ANTES de importar Django
# Esto soluciona el error "module 'importlib.metadata' has no attribute 'packages_distributions'"
# que ocurre en Python 3.9 con algunas librerías que esperan Python 3.10+
import sys
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

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')

application = get_wsgi_application()
