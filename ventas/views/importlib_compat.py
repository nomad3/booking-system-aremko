"""
Módulo de compatibilidad para manejar diferencias en importlib.metadata
entre versiones de Python.
"""
import sys

def patch_importlib_metadata():
    """
    Parcha importlib.metadata para añadir packages_distributions si no existe.
    Este método fue añadido en Python 3.10 y algunas librerías lo esperan.
    """
    try:
        import importlib.metadata as metadata

        # Si packages_distributions no existe, lo añadimos
        if not hasattr(metadata, 'packages_distributions'):
            def packages_distributions():
                """
                Implementación compatible para Python < 3.10
                Retorna un diccionario de paquete -> lista de distribuciones
                """
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

            # Añadir el método al módulo
            metadata.packages_distributions = packages_distributions

    except Exception as e:
        # Si hay algún error, lo ignoramos silenciosamente
        pass

# Aplicar el parche al importar este módulo
patch_importlib_metadata()