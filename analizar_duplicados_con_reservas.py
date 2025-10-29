"""
Script para analizar duplicados de teléfono CON DETALLE DE RESERVAS
Muestra las reservas asociadas a cada ID duplicado para decidir cuál mantener
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente, VentaReserva, ReservaServicio
from collections import defaultdict
from datetime import date

print("\n" + "="*100)
print("ANALISIS DETALLADO DE DUPLICADOS CON RESERVAS ASOCIADAS")
print("="*100 + "\n")

# Obtener todos los clientes
clientes = Cliente.objects.all()
total_clientes = clientes.count()

print(f"Total de clientes en la BD: {total_clientes}\n")

# Agrupar clientes por teléfono normalizado
telefonos_normalizados = defaultdict(list)

for cliente in clientes:
    telefono_original = cliente.telefono

    if telefono_original:
        telefono_normalizado = telefono_original if telefono_original.startswith('+') else f'+{telefono_original}'

        # Obtener reservas del cliente
        ventas = VentaReserva.objects.filter(cliente=cliente).order_by('-fecha_reserva')

        # Contar reservas por estado
        reservas_info = {
            'total': ventas.count(),
            'pendientes': ventas.filter(estado_reserva='pendiente').count(),
            'confirmadas': ventas.filter(estado_reserva='confirmada').count(),
            'canceladas': ventas.filter(estado_reserva='cancelada').count(),
            'ventas': []
        }

        # Obtener detalle de cada venta con fecha de check-in
        for venta in ventas:
            # Obtener la fecha más próxima de los servicios de esta venta
            servicios = ReservaServicio.objects.filter(venta_reserva=venta).order_by('fecha_agendamiento')
            fecha_checkin = servicios.first().fecha_agendamiento if servicios.exists() else None

            reservas_info['ventas'].append({
                'id': venta.id,
                'fecha_reserva': venta.fecha_reserva.date() if venta.fecha_reserva else None,
                'fecha_checkin': fecha_checkin,
                'estado': venta.estado_reserva,
                'estado_pago': venta.estado_pago,
                'total': float(venta.total),
                'num_servicios': servicios.count()
            })

        telefonos_normalizados[telefono_normalizado].append({
            'id': cliente.id,
            'nombre': cliente.nombre,
            'telefono_original': telefono_original,
            'email': cliente.email or 'sin email',
            'ciudad': cliente.ciudad or 'sin ciudad',
            'documento': cliente.documento_identidad or 'sin doc',
            'reservas': reservas_info
        })

# Encontrar duplicados
duplicados = {tel: clientes for tel, clientes in telefonos_normalizados.items() if len(clientes) > 1}

print("="*100)
print("RESULTADOS")
print("="*100 + "\n")

if duplicados:
    print(f"SE ENCONTRARON {len(duplicados)} NUMEROS CON DUPLICADOS\n")

    hoy = date.today()

    for i, (telefono_normalizado, clientes_dup) in enumerate(sorted(duplicados.items()), 1):
        print("\n" + "="*100)
        print(f"DUPLICADO #{i}: {telefono_normalizado}")
        print("="*100)

        for j, cliente in enumerate(clientes_dup, 1):
            reservas = cliente['reservas']

            # Contar reservas futuras
            reservas_futuras = sum(
                1 for v in reservas['ventas']
                if v['fecha_checkin'] and v['fecha_checkin'] >= hoy and v['estado'] != 'cancelada'
            )

            # Mostrar info del cliente
            print(f"\n[CLIENTE {j}] ID: {cliente['id']}")
            print(f"  Nombre:    {cliente['nombre']}")
            print(f"  Telefono:  {cliente['telefono_original']}")
            print(f"  Email:     {cliente['email']}")
            print(f"  Ciudad:    {cliente['ciudad']}")
            print(f"  Documento: {cliente['documento']}")
            print(f"\n  RESUMEN DE RESERVAS:")
            print(f"    Total reservas:     {reservas['total']}")
            print(f"    - Pendientes:       {reservas['pendientes']}")
            print(f"    - Confirmadas:      {reservas['confirmadas']}")
            print(f"    - Canceladas:       {reservas['canceladas']}")
            print(f"    - FUTURAS (activas): {reservas_futuras}")

            if reservas['ventas']:
                print(f"\n  DETALLE DE RESERVAS:")
                print(f"  {'ID':<8} {'F.Reserva':<12} {'F.CheckIn':<12} {'Estado':<12} {'Pago':<10} {'Total':>12} {'Serv':<4} {'Tipo':<8}")
                print(f"  {'-'*90}")

                for venta in reservas['ventas']:
                    fecha_reserva_str = str(venta['fecha_reserva']) if venta['fecha_reserva'] else 'Sin fecha'
                    fecha_checkin_str = str(venta['fecha_checkin']) if venta['fecha_checkin'] else 'Sin fecha'

                    # Determinar si es futura o pasada
                    if venta['fecha_checkin']:
                        if venta['fecha_checkin'] >= hoy:
                            tipo = "FUTURA" if venta['estado'] != 'cancelada' else "CANCEL"
                        else:
                            tipo = "PASADA"
                    else:
                        tipo = "???"

                    print(f"  {venta['id']:<8} {fecha_reserva_str:<12} {fecha_checkin_str:<12} "
                          f"{venta['estado']:<12} {venta['estado_pago']:<10} ${venta['total']:>11,.0f} "
                          f"{venta['num_servicios']:<4} {tipo:<8}")

        # RECOMENDACION
        print(f"\n{'='*100}")
        print("RECOMENDACION:")
        print("="*100)

        # Analizar cuál cliente tiene más información/reservas relevantes
        cliente_recomendado = None
        max_score = -1

        for cliente in clientes_dup:
            score = 0
            reservas = cliente['reservas']

            # Puntos por reservas futuras (más importante)
            reservas_futuras = sum(
                1 for v in reservas['ventas']
                if v['fecha_checkin'] and v['fecha_checkin'] >= hoy and v['estado'] != 'cancelada'
            )
            score += reservas_futuras * 10

            # Puntos por total de reservas
            score += reservas['total'] * 2

            # Puntos por datos completos
            if cliente['email'] != 'sin email':
                score += 1
            if cliente['ciudad'] != 'sin ciudad':
                score += 1
            if cliente['documento'] != 'sin doc':
                score += 1

            # Puntos por formato de teléfono correcto (con +)
            if cliente['telefono_original'].startswith('+'):
                score += 1

            if score > max_score:
                max_score = score
                cliente_recomendado = cliente

        if cliente_recomendado:
            print(f"  >> MANTENER: ID {cliente_recomendado['id']} - {cliente_recomendado['nombre']}")
            print(f"     Razones:")

            reservas_futuras_rec = sum(
                1 for v in cliente_recomendado['reservas']['ventas']
                if v['fecha_checkin'] and v['fecha_checkin'] >= hoy and v['estado'] != 'cancelada'
            )

            if reservas_futuras_rec > 0:
                print(f"     - Tiene {reservas_futuras_rec} reserva(s) FUTURA(S)")
            if cliente_recomendado['reservas']['total'] > 0:
                print(f"     - Tiene {cliente_recomendado['reservas']['total']} reserva(s) en total")
            if cliente_recomendado['telefono_original'].startswith('+'):
                print(f"     - Ya tiene formato correcto (+)")

            otros = [c for c in clientes_dup if c['id'] != cliente_recomendado['id']]
            if otros:
                print(f"\n  >> MIGRAR/ELIMINAR:")
                for otro in otros:
                    reservas_otro = sum(
                        1 for v in otro['reservas']['ventas']
                        if v['fecha_checkin'] and v['fecha_checkin'] >= hoy and v['estado'] != 'cancelada'
                    )
                    print(f"     - ID {otro['id']} ({otro['reservas']['total']} reservas, {reservas_otro} futuras)")
                    if otro['reservas']['total'] > 0:
                        print(f"       CUIDADO: Migrar sus {otro['reservas']['total']} reservas al ID {cliente_recomendado['id']}")

    # RESUMEN FINAL
    print("\n" + "="*100)
    print("RESUMEN EJECUTIVO")
    print("="*100 + "\n")

    total_registros_duplicados = sum(len(clientes) for clientes in duplicados.values())
    total_a_eliminar = total_registros_duplicados - len(duplicados)

    print(f"Total clientes duplicados:        {total_registros_duplicados}")
    print(f"Numeros unicos:                   {len(duplicados)}")
    print(f"Registros a consolidar:           {total_a_eliminar}")
    print(f"\nREDUCCION: De {total_clientes} a {total_clientes - total_a_eliminar} clientes")

    print("\n" + "="*100)
    print("PROXIMOS PASOS:")
    print("="*100)
    print("1. Revisar las RECOMENDACIONES arriba")
    print("2. Para cada duplicado:")
    print("   a) Si hay reservas FUTURAS: CUIDADO - deben migrarse")
    print("   b) Si solo hay reservas pasadas: Consolidar es seguro")
    print("   c) Usar el ID recomendado como destino")
    print("3. Ejecutar script de consolidacion con las decisiones")
    print("\n" + "="*100 + "\n")

else:
    print("No se encontraron duplicados.")
    print("\n" + "="*100 + "\n")
