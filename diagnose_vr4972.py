import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import VentaReserva, Comanda, ReservaProducto
import traceback

print("=== DIAGNÓSTICO VentaReserva 4972 ===\n")

try:
    # Verificar si existe
    print("1. Verificando VentaReserva 4972...")
    vr = VentaReserva.objects.filter(id=4972).first()

    if not vr:
        print("   ❌ VentaReserva 4972 NO existe")
        exit(1)

    print(f"   ✅ Existe: ID={vr.id}")
    print(f"   - Cliente: {vr.cliente}")
    print(f"   - Estado Reserva: {vr.estado_reserva}")
    print(f"   - Estado Pago: {vr.estado_pago}")

    # Verificar comandas asociadas
    print("\n2. Comandas asociadas:")
    comandas = Comanda.objects.filter(venta_reserva_id=4972)
    print(f"   Total: {comandas.count()}")

    for c in comandas:
        print(f"\n   Comanda #{c.id}:")
        print(f"   - Estado: {c.estado}")
        print(f"   - Creada: {c.fecha_solicitud}")
        print(f"   - Usuario solicita: {c.usuario_solicita}")
        print(f"   - Usuario procesa: {c.usuario_procesa}")
        print(f"   - Notas: {c.notas_generales[:50] if c.notas_generales else 'Sin notas'}")

        # Verificar detalles
        detalles = c.detalles.all()
        print(f"   - Detalles: {detalles.count()} items")

    # Verificar ReservaProducto
    print("\n3. ReservaProducto asociados:")
    rps = ReservaProducto.objects.filter(venta_reserva_id=4972)
    print(f"   Total: {rps.count()}")

    for rp in rps[:5]:  # Primeros 5
        print(f"   - {rp.cantidad}x {rp.producto} - ${rp.precio_unitario_venta}")

    # Probar métodos que podrían causar error
    print("\n4. Probando métodos potencialmente problemáticos...")

    # Probar __str__
    try:
        str_repr = str(vr)
        print(f"   ✅ __str__: {str_repr[:50]}")
    except Exception as e:
        print(f"   ❌ Error en __str__: {str(e)}")

    # Probar total property
    try:
        total = vr.total
        print(f"   ✅ total: ${total}")
    except Exception as e:
        print(f"   ❌ Error en total: {str(e)}")
        traceback.print_exc()

    # Probar otros métodos
    methods_to_test = ['pagado', 'cobrado', 'saldo_pendiente']
    for method in methods_to_test:
        try:
            if hasattr(vr, method):
                value = getattr(vr, method)
                print(f"   ✅ {method}: {value}")
        except Exception as e:
            print(f"   ❌ Error en {method}: {str(e)}")

    # Ver si hay datos inconsistentes
    print("\n5. Verificando consistencia de datos...")

    # Comandas sin detalles
    comandas_vacias = comandas.filter(detalles__isnull=True)
    if comandas_vacias.exists():
        print(f"   ⚠️  Hay {comandas_vacias.count()} comandas sin detalles")

    # Datos NULL inesperados
    if vr.cliente is None:
        print("   ⚠️  Cliente es NULL")

except Exception as e:
    print(f"\n❌ ERROR GENERAL: {type(e).__name__}: {str(e)}")
    traceback.print_exc()

print("\n=== FIN DIAGNÓSTICO ===")