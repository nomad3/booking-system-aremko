import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Comanda, DetalleComanda
import traceback

print("=== TEST COMANDA #22 ===\n")

try:
    # Obtener la comanda
    comanda = Comanda.objects.get(id=22)
    print(f"Comanda encontrada: #{comanda.id}")
    print(f"VentaReserva: {comanda.venta_reserva_id}")
    print(f"Estado: {comanda.estado}")

    # Verificar detalles
    print("\nDetalles de la comanda:")
    detalles = comanda.detalles.all()
    for d in detalles:
        print(f"  - {d.cantidad}x {d.producto}")
        print(f"    Precio: ${d.precio_unitario}")
        print(f"    Especificaciones: {d.especificaciones}")

    # Probar métodos
    print("\nProbando métodos de la comanda...")

    try:
        tiempo = comanda.tiempo_espera()
        print(f"  ✅ tiempo_espera(): {tiempo} minutos")
    except Exception as e:
        print(f"  ❌ tiempo_espera(): {str(e)}")

    try:
        str_repr = str(comanda)
        print(f"  ✅ __str__(): {str_repr}")
    except Exception as e:
        print(f"  ❌ __str__(): {str(e)}")

    # Ver si el problema es con el inline de comandas
    print("\nVerificando si el inline de comandas podría causar el error...")

    # Simular lo que haría ComandaInline
    try:
        from django.contrib import admin
        from ventas.admin import ComandaInline

        # Ver si ComandaInline tiene algún método problemático
        print("  Verificando ComandaInline...")

        # Buscar métodos display
        for attr in dir(ComandaInline):
            if attr.endswith('_display') or attr == 'get_readonly_fields':
                print(f"    - Método encontrado: {attr}")

    except Exception as e:
        print(f"  Error verificando inline: {str(e)}")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
    traceback.print_exc()

print("\n=== FIN TEST ===")