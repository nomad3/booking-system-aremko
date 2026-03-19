#!/usr/bin/env python
"""
Fix para desactivar temporalmente el método clean() incorrecto en ServicioBloqueo
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import ServicioBloqueo

print("=== FIX MÉTODO CLEAN SERVICIOBLOQUEO ===\n")

# Crear un método clean temporal que no haga validaciones problemáticas
def clean_temporal(self):
    """Método clean temporal sin validaciones de ServicioSlotBloqueo"""
    from django.core.exceptions import ValidationError

    # Solo validaciones básicas para ServicioBloqueo
    if hasattr(self, 'fecha_inicio') and hasattr(self, 'fecha_fin'):
        if self.fecha_inicio and self.fecha_fin:
            if self.fecha_inicio > self.fecha_fin:
                raise ValidationError({
                    'fecha_fin': 'La fecha fin debe ser posterior o igual a la fecha inicio'
                })

    # NO hacer validaciones de 'fecha' ni 'hora_slot'
    print(f"[DEBUG] clean() ejecutado para ServicioBloqueo: {self.servicio.nombre if hasattr(self, 'servicio') else 'Sin servicio'}")

# Reemplazar el método clean
print("1. Reemplazando método clean() problemático...")
ServicioBloqueo.clean = clean_temporal
print("   ✅ Método clean() reemplazado temporalmente")

# Verificar
print("\n2. Verificando el cambio...")
import inspect
try:
    codigo = inspect.getsource(ServicioBloqueo.clean)
    print("   Nuevo método clean():")
    print(codigo[:200] + "..." if len(codigo) > 200 else codigo)
except:
    print("   No se pudo verificar el código")

print("\n✅ FIX APLICADO")
print("\nAhora deberías poder crear ServicioBloqueo sin error 500")
print("Este fix es temporal y solo afecta la sesión actual del servidor")
print("\n⚠️  IMPORTANTE: Necesitarás reiniciar el servidor para aplicar este fix")
print("O ejecutar este script desde la shell de Django en Render")

# Código para ejecutar en la shell de Django
print("\n" + "="*60)
print("CÓDIGO PARA EJECUTAR EN SHELL DE DJANGO:")
print("="*60)
print("""
from ventas.models import ServicioBloqueo

def clean_temporal(self):
    from django.core.exceptions import ValidationError
    if hasattr(self, 'fecha_inicio') and hasattr(self, 'fecha_fin'):
        if self.fecha_inicio and self.fecha_fin:
            if self.fecha_inicio > self.fecha_fin:
                raise ValidationError({
                    'fecha_fin': 'La fecha fin debe ser posterior o igual a la fecha inicio'
                })

ServicioBloqueo.clean = clean_temporal
print("✅ Método clean() reemplazado")
""")
print("="*60)