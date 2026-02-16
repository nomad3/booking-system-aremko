# Script de diagnóstico para ejecutar desde Django Shell
# Uso: python3 manage.py shell < diagnostico_comandas_simple.py

from django.contrib.auth.models import User
from ventas.models import Comanda, DetalleComanda, VentaReserva, ReservaProducto, Producto
from django.utils import timezone
from decimal import Decimal

print("=" * 60)
print("DIAGNÓSTICO DEL SISTEMA DE COMANDAS")
print("Fecha:", timezone.now().strftime("%Y-%m-%d %H:%M:%S"))
print("=" * 60)

# 1. Verificar usuarios
print("\n=== Verificando Usuarios ===")
try:
    deborah = User.objects.get(username='Deborah')
    print(f"✅ Usuario Deborah existe (ID: {deborah.id})")
except User.DoesNotExist:
    print("❌ Usuario Deborah NO existe")

try:
    ernesto = User.objects.get(username='Ernesto')
    print(f"✅ Usuario Ernesto existe (ID: {ernesto.id})")
except User.DoesNotExist:
    print("❌ Usuario Ernesto NO existe")

# 2. Verificar productos
print("\n=== Verificando Productos ===")
productos_count = Producto.objects.count()
print(f"Total de productos: {productos_count}")
if productos_count > 0:
    print("Primeros 3 productos con precio:")
    for p in Producto.objects.all()[:3]:
        print(f"  - {p.nombre}: ${p.precio_base}")

# 3. Verificar VentaReservas
print("\n=== Verificando VentaReservas ===")
vr_count = VentaReserva.objects.count()
print(f"Total de VentaReservas: {vr_count}")
if vr_count > 0:
    print("Últimas 3 VentaReservas:")
    for r in VentaReserva.objects.all().order_by('-id')[:3]:
        cliente = r.cliente.nombre if r.cliente else "Sin cliente"
        print(f"  - ID: {r.id}, Cliente: {cliente}, Estado: {r.estado_reserva}")

# 4. Verificar comandas
print("\n=== Verificando Comandas ===")
comandas_count = Comanda.objects.count()
print(f"Total de comandas: {comandas_count}")
if comandas_count > 0:
    print("Últimas 3 comandas:")
    for c in Comanda.objects.all().order_by('-id')[:3]:
        detalles = c.detalles.count()
        vr_id = c.venta_reserva.id if c.venta_reserva else "Sin VR"
        print(f"  - ID: {c.id}, VentaReserva: {vr_id}, Estado: {c.estado}, Productos: {detalles}")

# 5. Verificar última comanda con detalles
print("\n=== Verificando Última Comanda con Detalles ===")
ultima_comanda = Comanda.objects.filter(detalles__isnull=False).order_by('-id').first()
if ultima_comanda:
    print(f"Comanda ID: {ultima_comanda.id}")
    print(f"VentaReserva: {ultima_comanda.venta_reserva.id if ultima_comanda.venta_reserva else 'Sin VR'}")
    print(f"Usuario solicita: {ultima_comanda.usuario_solicita}")
    print(f"Usuario procesa: {ultima_comanda.usuario_procesa}")
    print("\nDetalles:")
    for d in ultima_comanda.detalles.all():
        print(f"  - {d.cantidad}x {d.producto.nombre}")
        print(f"    Precio unitario: ${d.precio_unitario}")
        print(f"    Precio base producto: ${d.producto.precio_base}")
        print(f"    ¿Precios coinciden?: {'✅' if d.precio_unitario == d.producto.precio_base else '❌'}")
        if d.especificaciones:
            print(f"    Especificaciones: {d.especificaciones}")

    # Verificar ReservaProducto
    print("\nVerificando ReservaProducto asociados:")
    if ultima_comanda.venta_reserva:
        for d in ultima_comanda.detalles.all():
            rp = ReservaProducto.objects.filter(
                venta_reserva=ultima_comanda.venta_reserva,
                producto=d.producto
            ).first()
            if rp:
                print(f"  ✅ ReservaProducto existe para {d.producto.nombre}")
                print(f"     Notas: {rp.notas}")
            else:
                print(f"  ❌ NO existe ReservaProducto para {d.producto.nombre}")
else:
    print("No hay comandas con detalles en el sistema")

print("\n" + "=" * 60)
print("DIAGNÓSTICO COMPLETADO")
print("=" * 60)