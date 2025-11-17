# Signals package for ventas app

# Re-export functions from main_signals module for backward compatibility
from .main_signals import validar_disponibilidad_admin

__all__ = ['validar_disponibilidad_admin']
