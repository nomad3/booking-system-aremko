#!/usr/bin/env python
"""
Script para aplicar la migración 0071 del sistema de pagos a masajistas.
Ejecutar desde el shell de Render.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'booking_system.settings')
django.setup()

from django.core.management import execute_from_command_line

def main():
    print("=" * 60)
    print("APLICANDO MIGRACIÓN 0071 - SISTEMA DE PAGOS A MASAJISTAS")
    print("=" * 60)
    print()

    # Aplicar la migración específica
    print("Aplicando migración 0071_sistema_pagos_masajistas...")
    try:
        execute_from_command_line(['manage.py', 'migrate', 'ventas', '0071'])
        print("✅ Migración aplicada exitosamente")
    except Exception as e:
        print(f"❌ Error aplicando migración: {e}")
        return False

    print()
    print("=" * 60)
    print("VERIFICANDO LA MIGRACIÓN")
    print("=" * 60)
    print()

    # Verificar que los campos fueron agregados
    from ventas.models import Proveedor, PagoMasajista, DetalleServicioPago, ReservaServicio

    try:
        # Verificar campos en Proveedor
        proveedor_fields = [f.name for f in Proveedor._meta.get_fields()]
        required_proveedor_fields = [
            'porcentaje_comision', 'es_masajista', 'rut',
            'banco', 'tipo_cuenta', 'numero_cuenta'
        ]

        missing_proveedor = [f for f in required_proveedor_fields if f not in proveedor_fields]
        if missing_proveedor:
            print(f"⚠️  Campos faltantes en Proveedor: {missing_proveedor}")
        else:
            print("✅ Todos los campos de Proveedor fueron agregados correctamente")

        # Verificar que PagoMasajista existe
        pago_count = PagoMasajista.objects.count()
        print(f"✅ Modelo PagoMasajista creado correctamente (registros actuales: {pago_count})")

        # Verificar que DetalleServicioPago existe
        detalle_count = DetalleServicioPago.objects.count()
        print(f"✅ Modelo DetalleServicioPago creado correctamente (registros actuales: {detalle_count})")

        # Verificar campos en ReservaServicio
        reserva_fields = [f.name for f in ReservaServicio._meta.get_fields()]
        required_reserva_fields = ['pagado_a_proveedor', 'pago_proveedor']

        missing_reserva = [f for f in required_reserva_fields if f not in reserva_fields]
        if missing_reserva:
            print(f"⚠️  Campos faltantes en ReservaServicio: {missing_reserva}")
        else:
            print("✅ Todos los campos de ReservaServicio fueron agregados correctamente")

    except Exception as e:
        print(f"❌ Error verificando modelos: {e}")
        return False

    print()
    print("=" * 60)
    print("CONFIGURACIÓN INICIAL")
    print("=" * 60)
    print()

    # Marcar todos los masajistas existentes
    try:
        masajistas_actualizados = Proveedor.objects.filter(
            nombre__icontains='masajista'
        ).update(es_masajista=True)
        print(f"✅ {masajistas_actualizados} proveedores marcados como masajistas")

        # Configurar porcentaje de comisión por defecto
        sin_comision = Proveedor.objects.filter(
            es_masajista=True,
            porcentaje_comision=0
        ).update(porcentaje_comision=40.00)

        if sin_comision:
            print(f"✅ {sin_comision} masajistas configurados con comisión del 40% por defecto")

    except Exception as e:
        print(f"⚠️  Error configurando masajistas: {e}")

    # Mostrar estadísticas
    print()
    print("=" * 60)
    print("ESTADÍSTICAS DEL SISTEMA")
    print("=" * 60)
    print()

    try:
        total_masajistas = Proveedor.objects.filter(es_masajista=True).count()
        print(f"Total de masajistas en el sistema: {total_masajistas}")

        # Contar servicios pendientes de pago
        from django.db.models import Count
        servicios_pendientes = ReservaServicio.objects.filter(
            venta_reserva__estado='pagado',
            pagado_a_proveedor=False,
            proveedor_asignado__es_masajista=True
        ).count()

        print(f"Servicios pendientes de pago: {servicios_pendientes}")

    except Exception as e:
        print(f"⚠️  Error obteniendo estadísticas: {e}")

    print()
    print("=" * 60)
    print("✅ PROCESO COMPLETADO")
    print("=" * 60)
    print()
    print("El sistema de pagos a masajistas está listo para usar.")
    print("Acceso desde el menú: Admin > Servicios y Proveedores > Pagos a Masajistas")
    print()

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)