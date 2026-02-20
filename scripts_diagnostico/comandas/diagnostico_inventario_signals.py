#!/usr/bin/env python
"""
Diagnóstico específico del problema de inventario y signals
Ejecutar con: python manage.py shell < diagnostico_inventario_signals.py
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection, transaction
from django.db.models import signals
from ventas.models import ReservaProducto, Producto, VentaReserva
from django.utils import timezone

print("\n" + "=" * 80)
print("DIAGNÓSTICO DE INVENTARIO Y SIGNALS")
print("=" * 80)

# 1. Verificar el signal actualizar_inventario
print("\n1. ANALIZANDO SIGNAL actualizar_inventario")
print("-" * 40)

try:
    # Buscar receivers conectados a post_save de ReservaProducto
    from django.db.models.signals import post_save, post_delete

    print("Signals conectados a ReservaProducto:")

    # Para post_save
    if hasattr(post_save, '_live_receivers'):
        for receiver in post_save._live_receivers:
            if hasattr(receiver, 'sender') and receiver.sender:
                sender_name = getattr(receiver.sender, '__name__', str(receiver.sender))
                if 'ReservaProducto' in sender_name:
                    print(f"  - post_save: {receiver}")

    # Para post_delete
    if hasattr(post_delete, '_live_receivers'):
        for receiver in post_delete._live_receivers:
            if hasattr(receiver, 'sender') and receiver.sender:
                sender_name = getattr(receiver.sender, '__name__', str(receiver.sender))
                if 'ReservaProducto' in sender_name:
                    print(f"  - post_delete: {receiver}")

except Exception as e:
    print(f"✗ Error verificando signals: {e}")

# 2. Buscar el código del signal
print("\n2. BUSCANDO CÓDIGO DEL SIGNAL")
print("-" * 40)

try:
    # Intentar importar el módulo signals de ventas
    try:
        from ventas import signals as ventas_signals
        print("✓ Módulo ventas.signals importado")

        # Listar funciones en el módulo
        signal_functions = [item for item in dir(ventas_signals)
                          if not item.startswith('_') and callable(getattr(ventas_signals, item))]
        print(f"Funciones encontradas: {signal_functions}")

    except ImportError:
        print("✗ No se pudo importar ventas.signals")

except Exception as e:
    print(f"✗ Error: {e}")

# 3. Probar comportamiento con productos
print("\n3. PROBANDO COMPORTAMIENTO DE INVENTARIO")
print("-" * 40)

try:
    # Buscar un producto con stock
    producto_test = Producto.objects.filter(
        publicado_web=True,
        stock__gt=5
    ).first()

    if producto_test:
        print(f"Producto de prueba: {producto_test.nombre}")
        print(f"  Stock actual: {producto_test.stock}")
        print(f"  Precio: ${producto_test.precio}")

        # Simular qué pasaría al crear ReservaProducto
        print("\nSimulando creación de ReservaProducto con cantidad=2...")
        print("(Sin guardar realmente)")

        # Verificar si hay suficiente stock
        cantidad_prueba = 2
        if producto_test.stock >= cantidad_prueba:
            print(f"✓ Stock suficiente ({producto_test.stock} >= {cantidad_prueba})")
        else:
            print(f"✗ Stock insuficiente ({producto_test.stock} < {cantidad_prueba})")

    else:
        print("✗ No hay productos con stock > 5 para prueba")

except Exception as e:
    print(f"✗ Error en prueba: {e}")

# 4. Verificar transacciones en ReservaProducto
print("\n4. ANALIZANDO GUARDADO DE ReservaProducto")
print("-" * 40)

try:
    # Ver si hay ReservaProducto recientes
    reservas_producto = ReservaProducto.objects.order_by('-id')[:5]

    print(f"Últimas {len(reservas_producto)} ReservaProducto:")
    for rp in reservas_producto:
        print(f"  ID: {rp.id}")
        print(f"    Producto: {rp.producto.nombre if rp.producto else 'SIN PRODUCTO'}")
        print(f"    Cantidad: {rp.cantidad}")
        print(f"    Subtotal: ${rp.subtotal}")
        print(f"    VentaReserva: {rp.venta_reserva_id}")
        print()

except Exception as e:
    print(f"✗ Error: {e}")

# 5. Probar guardado con transacción
print("\n5. PRUEBA DE GUARDADO CON TRANSACCIÓN")
print("-" * 40)

try:
    # Buscar una reserva de prueba
    reserva = VentaReserva.objects.filter(
        fecha__date=timezone.now().date()
    ).first()

    if not reserva:
        # Crear una reserva temporal
        print("No hay reservas de hoy, creando una temporal...")
        from django.contrib.auth import get_user_model
        User = get_user_model()
        usuario = User.objects.filter(is_superuser=True).first()

        if usuario:
            reserva = VentaReserva.objects.create(
                fecha=timezone.now(),
                hora='10:00',
                usuario=usuario,
                total=0,
                estado_pago='pendiente'
            )
            print(f"✓ Reserva temporal creada: {reserva.id}")

    if reserva and producto_test:
        print(f"\nIntentando crear ReservaProducto:")
        print(f"  Reserva: {reserva.id}")
        print(f"  Producto: {producto_test.nombre}")
        print(f"  Cantidad: 1")

        # Usar transacción para capturar el error
        try:
            with transaction.atomic():
                rp = ReservaProducto(
                    venta_reserva=reserva,
                    producto=producto_test,
                    cantidad=1,
                    precio_unitario=producto_test.precio,
                    subtotal=producto_test.precio
                )
                # No guardamos realmente, solo verificamos
                print("✓ ReservaProducto se puede crear (sin guardar)")

                # Ahora intentar guardar de verdad (comentado por seguridad)
                # rp.save()
                # print("✓ ReservaProducto guardado exitosamente")

        except Exception as e:
            print(f"✗ Error al intentar crear/guardar: {type(e).__name__}: {e}")

    else:
        print("✗ No se puede hacer la prueba sin reserva o producto")

except Exception as e:
    print(f"✗ Error en prueba: {e}")

# 6. Verificar método save de modelos
print("\n6. VERIFICANDO MÉTODOS SAVE")
print("-" * 40)

try:
    # Verificar si ReservaProducto tiene save personalizado
    if hasattr(ReservaProducto, 'save'):
        import inspect
        save_method = getattr(ReservaProducto, 'save')
        if not inspect.isbuiltin(save_method):
            print("✓ ReservaProducto tiene método save personalizado")
            # Intentar ver el código
            try:
                import dis
                print("Bytecode del método save:")
                dis.dis(save_method)
            except:
                pass
    else:
        print("ReservaProducto usa save por defecto")

except Exception as e:
    print(f"✗ Error: {e}")

# 7. Resumen
print("\n" + "=" * 80)
print("ANÁLISIS DEL PROBLEMA")
print("=" * 80)

print("\nHIPÓTESIS DEL ERROR ORIGINAL:")
print("-" * 40)
print("1. El signal actualizar_inventario se ejecuta en post_save de ReservaProducto")
print("2. El signal intenta reducir el stock del producto")
print("3. Si no hay suficiente stock, el signal lanza ValueError")
print("4. Esto causa que falle el guardado de la comanda completa")
print()
print("SOLUCIONES POSIBLES:")
print("-" * 40)
print("1. VALIDAR ANTES: Verificar stock antes de crear ReservaProducto")
print("2. SIGNAL TOLERANTE: Modificar signal para que no lance excepción")
print("3. TRANSACCIÓN: Usar savepoint para revertir solo productos sin stock")
print("4. DESHABILITAR: Temporalmente deshabilitar el signal (no recomendado)")
print()
print("RECOMENDACIÓN:")
print("Implementar validación de stock en el método save_formset del admin")
print("antes de intentar guardar los ReservaProducto.")

print("\n" + "=" * 80)