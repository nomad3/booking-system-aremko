"""
Verifica el formato de teléfonos en la tabla Cliente
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente

# Obtener sample de teléfonos
clientes = Cliente.objects.filter(telefono__isnull=False).exclude(telefono='')[:20]

print('=== SAMPLE DE TELÉFONOS EN LA TABLA CLIENTES ===\n')
print(f'{'ID':<6} {'NOMBRE':<30} {'TELÉFONO':<20}')
print('-' * 60)

for c in clientes:
    print(f'{c.id:<6} {c.nombre[:30]:<30} {c.telefono:<20}')

# Estadísticas de formato
print('\n=== ANÁLISIS DE FORMATO ===\n')
todos_telefonos = list(Cliente.objects.filter(telefono__isnull=False).exclude(telefono='').values_list('telefono', flat=True))

with_plus = sum(1 for t in todos_telefonos if str(t).startswith('+'))
with_56 = sum(1 for t in todos_telefonos if str(t).startswith('56') and not str(t).startswith('+'))
other = len(todos_telefonos) - with_plus - with_56

print(f'Con + al inicio: {with_plus:,}')
print(f'Con 56 (sin +): {with_56:,}')
print(f'Otro formato: {other:,}')
print(f'Total: {len(todos_telefonos):,}')

# Ejemplos de cada formato
print('\n=== EJEMPLOS POR FORMATO ===\n')
if with_plus > 0:
    print('Con +:', [t for t in todos_telefonos if str(t).startswith('+')][:3])
if with_56 > 0:
    print('Con 56:', [t for t in todos_telefonos if str(t).startswith('56') and not str(t).startswith('+')][:3])
if other > 0:
    print('Otro:', [t for t in todos_telefonos if not str(t).startswith('56') and not str(t).startswith('+')][:3])
