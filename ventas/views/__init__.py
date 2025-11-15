# This file makes the 'views' directory a Python package.

# Aplicar parche de compatibilidad para importlib.metadata
# Esto soluciona el error "module 'importlib.metadata' has no attribute 'packages_distributions'"
# que ocurre en Python 3.9 con algunas librerías que esperan Python 3.10+
try:
    from . import importlib_compat
except Exception:
    # Si falla el parche, continuar de todos modos
    pass
