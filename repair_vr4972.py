import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import VentaReserva, Comanda, ReservaProducto
from django.db import transaction

print("=== REPARAR VentaReserva 4972 ===\n")

try:
    # Primero diagnosticar
    vr = VentaReserva.objects.get(id=4972)
    print(f"VentaReserva encontrada: {vr.id}")

    # Opción 1: Eliminar comandas problemáticas
    print("\n1. Buscando comandas recientes (últimas 2 horas)...")
    from django.utils import timezone
    from datetime import timedelta

    recent_time = timezone.now() - timedelta(hours=2)
    comandas_recientes = Comanda.objects.filter(
        venta_reserva_id=4972,
        fecha_solicitud__gte=recent_time
    )

    if comandas_recientes.exists():
        print(f"   Encontradas {comandas_recientes.count()} comandas recientes:")
        for c in comandas_recientes:
            print(f"   - Comanda #{c.id} creada {c.fecha_solicitud}")
            print(f"     Estado: {c.estado}")
            print(f"     Detalles: {c.detalles.count()}")

        respuesta = input("\n¿Deseas ELIMINAR estas comandas recientes? (s/n): ")
        if respuesta.lower() == 's':
            with transaction.atomic():
                count = comandas_recientes.count()
                comandas_recientes.delete()
                print(f"   ✅ {count} comandas eliminadas")

    # Opción 2: Verificar y limpiar ReservaProducto huérfanos
    print("\n2. Verificando ReservaProducto...")

    # Buscar duplicados
    from django.db.models import Count
    duplicados = ReservaProducto.objects.filter(
        venta_reserva_id=4972
    ).values('producto').annotate(
        count=Count('id')
    ).filter(count__gt=1)

    if duplicados:
        print("   ⚠️  Encontrados productos duplicados:")
        for dup in duplicados:
            print(f"   - Producto ID {dup['producto']}: {dup['count']} veces")

        respuesta = input("\n¿Deseas ELIMINAR duplicados (mantener solo uno)? (s/n): ")
        if respuesta.lower() == 's':
            with transaction.atomic():
                for dup in duplicados:
                    # Mantener el primero, eliminar el resto
                    rps = ReservaProducto.objects.filter(
                        venta_reserva_id=4972,
                        producto_id=dup['producto']
                    ).order_by('id')

                    # Eliminar todos menos el primero
                    for rp in rps[1:]:
                        rp.delete()
                        print(f"   ✅ Eliminado duplicado: {rp}")

    # Verificar si ahora funciona
    print("\n3. Verificando si VentaReserva funciona ahora...")
    try:
        # Probar operaciones comunes
        str(vr)
        vr.total
        vr.pagado
        vr.saldo_pendiente
        print("   ✅ Todas las operaciones funcionan correctamente")
    except Exception as e:
        print(f"   ❌ Todavía hay errores: {str(e)}")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN REPARACIÓN ===")