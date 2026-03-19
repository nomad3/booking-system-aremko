#!/usr/bin/env python
"""
Fix completo para ServicioBloqueo - corrige el modelo en el servidor
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

print("=== FIX COMPLETO SERVICIOBLOQUEO ===\n")
print("Este script corrige el modelo ServicioBloqueo que tiene métodos mezclados\n")

# El código correcto del método clean para ServicioBloqueo
CLEAN_METHOD_CORRECTO = '''
def clean(self):
    """Validaciones del modelo ServicioBloqueo"""
    from django.core.exceptions import ValidationError
    from .models import ReservaServicio

    # Validar que fecha_inicio no sea mayor que fecha_fin
    if self.fecha_inicio > self.fecha_fin:
        raise ValidationError({
            'fecha_fin': 'La fecha de fin debe ser posterior o igual a la fecha de inicio'
        })

    # Validar que no haya reservas existentes en el rango
    reservas_existentes = ReservaServicio.objects.filter(
        servicio=self.servicio,
        fecha_agendamiento__range=[self.fecha_inicio, self.fecha_fin]
    ).exists()

    if reservas_existentes:
        raise ValidationError({
            'fecha_inicio': 'Ya existen reservas en este rango de fechas. No se puede bloquear.'
        })
'''

print("1. Creando archivo Python con el modelo corregido...")

modelo_corregido = '''# Parche temporal para ServicioBloqueo
from ventas.models import ServicioBloqueo as ServicioBloqueoOriginal
from django.core.exceptions import ValidationError

# Guardar el método clean original (por si acaso)
_original_clean = getattr(ServicioBloqueoOriginal, 'clean', None)

# Definir el método clean correcto
def clean_correcto(self):
    """Validaciones del modelo ServicioBloqueo"""
    from ventas.models import ReservaServicio

    # Validar que fecha_inicio no sea mayor que fecha_fin
    if hasattr(self, 'fecha_inicio') and hasattr(self, 'fecha_fin'):
        if self.fecha_inicio and self.fecha_fin:
            if self.fecha_inicio > self.fecha_fin:
                raise ValidationError({
                    'fecha_fin': 'La fecha de fin debe ser posterior o igual a la fecha de inicio'
                })

            # Validar que no haya reservas existentes en el rango
            reservas_existentes = ReservaServicio.objects.filter(
                servicio=self.servicio,
                fecha_agendamiento__range=[self.fecha_inicio, self.fecha_fin]
            ).exists()

            if reservas_existentes:
                raise ValidationError({
                    'fecha_inicio': 'Ya existen reservas en este rango de fechas. No se puede bloquear.'
                })

# Aplicar el parche
ServicioBloqueoOriginal.clean = clean_correcto
print("✅ Método clean() de ServicioBloqueo corregido")
'''

# Guardar el parche
with open('parche_serviciobloqueo.py', 'w') as f:
    f.write(modelo_corregido)

print("   ✅ Archivo 'parche_serviciobloqueo.py' creado")

print("\n2. Instrucciones para aplicar el fix en Render:\n")
print("   OPCIÓN A - Shell de Django:")
print("   1. Accede a la shell: python manage.py shell")
print("   2. Ejecuta: exec(open('parche_serviciobloqueo.py').read())")
print("\n   OPCIÓN B - Comando directo:")
print("   python -c \"exec(open('parche_serviciobloqueo.py').read())\"")

print("\n3. Para hacer el fix permanente, agrega esto a ventas/__init__.py:")
print("   # Parche temporal para ServicioBloqueo")
print("   from . import parche_serviciobloqueo")

print("\n" + "="*60)
print("CÓDIGO MÍNIMO PARA COPIAR Y PEGAR EN SHELL:")
print("="*60)
print("""
from ventas.models import ServicioBloqueo
from django.core.exceptions import ValidationError

def clean_correcto(self):
    if hasattr(self, 'fecha_inicio') and hasattr(self, 'fecha_fin'):
        if self.fecha_inicio and self.fecha_fin:
            if self.fecha_inicio > self.fecha_fin:
                raise ValidationError({'fecha_fin': 'Debe ser posterior a fecha inicio'})

ServicioBloqueo.clean = clean_correcto
print("✅ Fix aplicado")
""")
print("="*60)

print("\n✅ FIX COMPLETO PREPARADO")