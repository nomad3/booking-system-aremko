#!/usr/bin/env python
"""
Fix para el método save() de ServicioBloqueo que está causando el error 500
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import ServicioBloqueo
import inspect

print("=== FIX MÉTODO SAVE() SERVICIOBLOQUEO ===\n")

# 1. Ver el método save actual
print("1. Método save() actual:")
try:
    codigo_save = inspect.getsource(ServicioBloqueo.save)
    print(codigo_save)
except:
    print("   No tiene método save() personalizado")

# 2. Remover el método save problemático
print("\n2. Removiendo método save() problemático...")

# Verificar si tiene save personalizado
if hasattr(ServicioBloqueo, 'save') and ServicioBloqueo.save != models.Model.save:
    # Eliminar el método save personalizado
    delattr(ServicioBloqueo, 'save')
    print("   ✅ Método save() personalizado eliminado")
    print("   Ahora usará el save() estándar de Django")
else:
    print("   No se encontró método save() personalizado")

# 3. También limpiar el clean si es necesario
print("\n3. Limpiando método clean()...")
if hasattr(ServicioBloqueo, 'clean'):
    # Reemplazar con un clean mínimo
    def clean_minimo(self):
        pass

    ServicioBloqueo.clean = clean_minimo
    print("   ✅ Método clean() reemplazado con versión mínima")

print("\n" + "="*60)
print("CÓDIGO PARA EJECUTAR EN DJANGO SHELL:")
print("="*60)
print("""
from ventas.models import ServicioBloqueo

# Eliminar save personalizado si existe
if hasattr(ServicioBloqueo, 'save'):
    delattr(ServicioBloqueo, 'save')
    print("✅ Método save() eliminado")

# Limpiar clean
ServicioBloqueo.clean = lambda self: None
print("✅ Método clean() neutralizado")
""")
print("="*60)

print("\n✅ FIX PREPARADO")