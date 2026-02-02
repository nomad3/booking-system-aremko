#!/usr/bin/env python
"""
Script de diagnóstico para la agenda operativa
Ejecutar en shell de Render: python diagnose_agenda.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.utils import timezone
from datetime import datetime, time, timedelta
from ventas.models import VentaReserva, ReservaServicio, ReservaProducto

def diagnose_agenda():
    print("\n" + "="*60)
    print("DIAGNÓSTICO DE AGENDA OPERATIVA")
    print("="*60)

    # Obtener hora actual
    ahora = timezone.localtime(timezone.now())
    hoy = ahora.date()
    hora_actual = ahora.time()

    print(f"\n📅 Fecha HOY: {hoy.strftime('%d/%m/%Y')}")
    print(f"⏰ Hora actual (Chile): {hora_actual.strftime('%H:%M:%S')}")
    print("-" * 60)

    # 1. Buscar servicios de hoy
    print("\n1️⃣ SERVICIOS DE HOY (no cancelados, no descuentos):")
    print("-" * 40)

    servicios_hoy = ReservaServicio.objects.filter(
        fecha_agendamiento=hoy,
        venta_reserva__isnull=False
    ).exclude(
        venta_reserva__estado_reserva='cancelada'
    ).exclude(
        servicio__nombre__icontains='descuento'
    ).select_related('servicio', 'venta_reserva__cliente').order_by('hora_inicio')

    print(f"Total servicios encontrados: {servicios_hoy.count()}")

    if servicios_hoy.count() == 0:
        print("❌ No hay servicios para hoy")
        return

    # 2. Mostrar servicios pendientes o en curso
    print("\n2️⃣ SERVICIOS PENDIENTES O EN CURSO:")
    print("-" * 40)

    servicios_visibles = []
    for servicio in servicios_hoy:
        try:
            if not servicio.hora_inicio:
                continue

            servicio_hora = datetime.strptime(servicio.hora_inicio, '%H:%M').time()

            # Calcular hora fin
            hora_fin = None
            if servicio.servicio and hasattr(servicio.servicio, 'duracion') and servicio.servicio.duracion:
                hora_inicio_dt = datetime.combine(hoy, servicio_hora)
                hora_fin_dt = hora_inicio_dt + timedelta(minutes=int(servicio.servicio.duracion))
                hora_fin = hora_fin_dt.time()

            # Verificar si es visible
            es_futuro = servicio_hora >= hora_actual
            en_curso = False
            if hora_fin:
                en_curso = servicio_hora < hora_actual and hora_fin > hora_actual

            if es_futuro or en_curso:
                servicios_visibles.append(servicio)
                estado = "EN CURSO 🟢" if en_curso else "PENDIENTE ⏳"
                print(f"  {servicio.hora_inicio} - {servicio.servicio.nombre if servicio.servicio else 'N/A'}")
                print(f"        Cliente: {servicio.venta_reserva.cliente.nombre if servicio.venta_reserva.cliente else 'N/A'}")
                print(f"        Reserva: #{servicio.venta_reserva.id}")
                print(f"        Estado: {estado}")
                if hora_fin:
                    print(f"        Termina: {hora_fin.strftime('%H:%M')}")
        except Exception as e:
            print(f"  ❌ Error procesando servicio: {e}")

    print(f"\nTotal servicios visibles: {len(servicios_visibles)}")

    # 3. Diagnosticar productos para una reserva específica
    print("\n3️⃣ DIAGNÓSTICO DE PRODUCTOS POR RESERVA:")
    print("-" * 40)

    # Buscar una reserva con servicios hoy
    if servicios_visibles:
        servicio_ejemplo = servicios_visibles[0]
        reserva = servicio_ejemplo.venta_reserva

        print(f"\n📌 Analizando Reserva #{reserva.id}")
        print(f"   Cliente: {reserva.cliente.nombre if reserva.cliente else 'N/A'}")

        # Obtener todos los productos
        productos = ReservaProducto.objects.filter(
            venta_reserva=reserva
        ).select_related('producto')

        print(f"\n   PRODUCTOS DE LA RESERVA ({productos.count()} total):")

        productos_normales = []
        productos_descuento = []

        for producto in productos:
            if not producto.producto:
                print(f"     ❌ Producto sin información")
                continue

            nombre = str(producto.producto.nombre or "").strip()
            precio = float(producto.producto.precio_base or 0)

            # Verificar si es descuento
            es_descuento = any([
                'descuento' in nombre.lower(),
                'discount' in nombre.lower(),
                'dto' in nombre.lower(),
                precio < 0,
                nombre.startswith('-'),
            ])

            if es_descuento:
                productos_descuento.append(producto)
                print(f"     🚫 DESCUENTO: {producto.cantidad}x {nombre} (${precio:,.0f})")
            else:
                productos_normales.append(producto)
                print(f"     ✅ NORMAL: {producto.cantidad}x {nombre} (${precio:,.0f})")
                print(f"        Fecha entrega: {producto.fecha_entrega or 'Sin fecha'}")

        print(f"\n   RESUMEN:")
        print(f"   - Productos normales: {len(productos_normales)} (deberían aparecer)")
        print(f"   - Productos descuento: {len(productos_descuento)} (NO deben aparecer)")

        # 4. Simular la lógica actual
        print("\n4️⃣ SIMULACIÓN DE LA LÓGICA ACTUAL:")
        print("-" * 40)

        print(f"\nServicio: {servicio_ejemplo.servicio.nombre if servicio_ejemplo.servicio else 'N/A'}")
        print(f"Hora: {servicio_ejemplo.hora_inicio}")

        productos_a_mostrar = []
        for producto in productos:
            if not producto.producto:
                continue

            try:
                nombre_producto = str(producto.producto.nombre or "").strip()
                precio_producto = float(producto.producto.precio_base or 0)

                es_descuento = any([
                    'descuento' in nombre_producto.lower(),
                    'discount' in nombre_producto.lower(),
                    'dto' in nombre_producto.lower(),
                    precio_producto < 0,
                    nombre_producto.startswith('-'),
                ])

                if not es_descuento:
                    productos_a_mostrar.append(producto)
            except Exception:
                continue

        print(f"\nProductos que deberían aparecer: {len(productos_a_mostrar)}")
        for p in productos_a_mostrar:
            print(f"  - {p.cantidad}x {p.producto.nombre}")

    # 5. Buscar reserva específica si se pasa como argumento
    if len(sys.argv) > 1:
        reserva_id = sys.argv[1]
        print(f"\n5️⃣ BÚSQUEDA ESPECÍFICA - RESERVA #{reserva_id}")
        print("-" * 40)

        try:
            reserva = VentaReserva.objects.get(id=reserva_id)

            # Servicios de esta reserva hoy
            servicios_reserva = ReservaServicio.objects.filter(
                venta_reserva=reserva,
                fecha_agendamiento=hoy
            ).exclude(
                servicio__nombre__icontains='descuento'
            )

            print(f"Servicios hoy: {servicios_reserva.count()}")
            for srv in servicios_reserva:
                print(f"  - {srv.hora_inicio}: {srv.servicio.nombre if srv.servicio else 'N/A'}")

            # Productos
            productos = ReservaProducto.objects.filter(venta_reserva=reserva).select_related('producto')
            print(f"\nProductos totales: {productos.count()}")

            for prod in productos:
                if prod.producto:
                    nombre = prod.producto.nombre
                    es_descuento = 'descuento' in nombre.lower() or prod.producto.precio_base < 0
                    marca = "🚫 DESCUENTO" if es_descuento else "✅ NORMAL"
                    print(f"  {marca}: {prod.cantidad}x {nombre}")

        except VentaReserva.DoesNotExist:
            print(f"❌ Reserva #{reserva_id} no encontrada")

    print("\n" + "="*60)
    print("FIN DEL DIAGNÓSTICO")
    print("="*60)

if __name__ == "__main__":
    diagnose_agenda()