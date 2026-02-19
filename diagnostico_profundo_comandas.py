#!/usr/bin/env python
"""
Diagnóstico profundo del error con comandas
Ejecutar con: python manage.py shell < diagnostico_profundo_comandas.py
"""

import os
import django
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import VentaReserva, Comanda
from ventas.admin import VentaReservaAdmin, ComandaInline
from django.contrib.admin.sites import site

print("\n" + "=" * 80)
print("DIAGNÓSTICO PROFUNDO - ERROR CON COMANDAS")
print("=" * 80)
print()

# 1. Verificar reservas con comandas
print("1. RESERVAS CON COMANDAS")
print("-" * 40)

reservas_con_comandas = VentaReserva.objects.filter(comandas__isnull=False).distinct()[:5]
print(f"Reservas con comandas encontradas: {reservas_con_comandas.count()}")

for reserva in reservas_con_comandas:
    print(f"\nReserva ID: {reserva.id}")
    print(f"  Cliente: {reserva.cliente}")
    print(f"  Comandas: {reserva.comandas.count()}")

# 2. Probar métodos del inline
print("\n\n2. VERIFICANDO ComandaInline")
print("-" * 40)

# Obtener una reserva con comandas
reserva_test = VentaReserva.objects.filter(id__in=[5002, 5009]).first()
if not reserva_test:
    reserva_test = reservas_con_comandas.first()

if reserva_test:
    print(f"Probando con reserva ID: {reserva_test.id}")

    # Verificar si el inline tiene métodos problemáticos
    inline = ComandaInline(VentaReserva, site)

    # Verificar campos y métodos
    print("\nCampos del inline:")
    print(f"  fields: {inline.fields}")
    print(f"  readonly_fields: {inline.readonly_fields}")

    # Probar acceso a comandas
    print("\nProbando acceso a comandas:")
    for comanda in reserva_test.comandas.all()[:3]:
        try:
            print(f"\n  Comanda ID: {comanda.id}")

            # Probar métodos que podrían fallar
            problemas = []

            # estado_badge
            try:
                if hasattr(inline, 'estado_badge'):
                    resultado = inline.estado_badge(comanda)
                    print(f"    estado_badge: OK")
            except Exception as e:
                problemas.append(f"estado_badge: {e}")

            # total_productos
            try:
                if hasattr(inline, 'total_productos'):
                    resultado = inline.total_productos(comanda)
                    print(f"    total_productos: {resultado}")
            except Exception as e:
                problemas.append(f"total_productos: {e}")

            # tiempo_espera_display
            try:
                if hasattr(inline, 'tiempo_espera_display'):
                    resultado = inline.tiempo_espera_display(comanda)
                    print(f"    tiempo_espera_display: OK")
            except Exception as e:
                problemas.append(f"tiempo_espera_display: {e}")

            # total_items (property del modelo)
            try:
                total = comanda.total_items
                print(f"    total_items: {total}")
            except Exception as e:
                problemas.append(f"total_items: {e}")

            # total_precio (property del modelo)
            try:
                precio = comanda.total_precio
                print(f"    total_precio: {precio}")
            except Exception as e:
                problemas.append(f"total_precio: {e}")

            if problemas:
                print(f"    ✗ PROBLEMAS ENCONTRADOS:")
                for p in problemas:
                    print(f"      - {p}")

        except Exception as e:
            print(f"  ✗ Error general con comanda {comanda.id}: {e}")
            traceback.print_exc()

# 3. Verificar el modelo Comanda
print("\n\n3. VERIFICANDO PROPIEDADES DEL MODELO COMANDA")
print("-" * 40)

# Obtener una comanda de las reservas problemáticas
comanda_problema = Comanda.objects.filter(venta_reserva_id__in=[5002, 5009]).first()

if comanda_problema:
    print(f"Probando comanda ID: {comanda_problema.id}")

    propiedades = ['total_items', 'total_precio', 'tiempo_espera']
    for prop in propiedades:
        try:
            valor = getattr(comanda_problema, prop, None)
            if callable(valor):
                valor = valor()
            print(f"  {prop}: {valor}")
        except Exception as e:
            print(f"  ✗ {prop}: ERROR - {e}")

# 4. Verificar campos calculados
print("\n\n4. POSIBLE SOLUCIÓN")
print("-" * 40)

print("El error puede estar en:")
print("1. ComandaInline fields que incluyen métodos/propiedades problemáticos")
print("2. Propiedades del modelo Comanda que fallan con ciertos datos")
print("3. El inline intenta mostrar campos que no existen o fallan")

print("\nPara solucionarlo temporalmente, edita ventas/admin.py:")
print("En ComandaInline (alrededor de línea 253), simplifica los fields:")
print()
print("fields = ('id', 'estado', 'fecha_solicitud')")
print()
print("Esto eliminará los campos problemáticos del inline.")

print("\n" + "=" * 80)
print("FIN DEL DIAGNÓSTICO")
print("=" * 80)