#!/usr/bin/env python
"""
Script para verificar el estado de servicios en la agenda operativa
"""

import os
import sys
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.utils import timezone
from ventas.models import ReservaServicio

def check_agenda():
    # Obtener hora actual en Chile
    ahora = timezone.localtime(timezone.now())
    hoy = ahora.date()
    hora_actual = ahora.time()

    print(f"\n=== VERIFICACIÓN DE AGENDA OPERATIVA ===")
    print(f"Fecha: {hoy.strftime('%d/%m/%Y')}")
    print(f"Hora actual (Chile): {hora_actual.strftime('%H:%M')}")
    print("-" * 50)

    # Contar todos los servicios de hoy
    servicios_hoy = ReservaServicio.objects.filter(
        fecha_agendamiento=hoy
    ).exclude(
        servicio__nombre__icontains='descuento'
    ).select_related('servicio', 'venta_reserva')

    print(f"\nTotal servicios hoy: {servicios_hoy.count()}")

    # Mostrar primeros servicios
    print("\nPrimeros servicios del día:")
    for srv in servicios_hoy[:5]:
        estado = srv.venta_reserva.estado_reserva if srv.venta_reserva else "sin_reserva"
        print(f"  - {srv.hora_inicio}: {srv.servicio.nombre if srv.servicio else 'Sin servicio'} ({estado})")

    # Contar servicios activos (no cancelados)
    servicios_activos = servicios_hoy.exclude(
        venta_reserva__estado_reserva='cancelada'
    )
    print(f"\nServicios activos (no cancelados): {servicios_activos.count()}")

    # Contar servicios pendientes o en curso
    pendientes_count = 0
    en_curso_count = 0

    for srv in servicios_activos:
        try:
            srv_hora = datetime.strptime(srv.hora_inicio, '%H:%M').time()

            # Calcular hora fin si hay duración
            if srv.servicio and srv.servicio.duracion:
                hora_inicio_dt = datetime.combine(hoy, srv_hora)
                hora_fin_dt = hora_inicio_dt + timezone.timedelta(minutes=srv.servicio.duracion)
                hora_fin = hora_fin_dt.time()

                if srv_hora >= hora_actual:
                    pendientes_count += 1
                elif srv_hora < hora_actual and hora_fin > hora_actual:
                    en_curso_count += 1
            else:
                if srv_hora >= hora_actual:
                    pendientes_count += 1
        except:
            pass

    print(f"\nServicios desde hora actual ({hora_actual.strftime('%H:%M')}):")
    print(f"  - Pendientes (futuros): {pendientes_count}")
    print(f"  - En curso ahora: {en_curso_count}")
    print(f"  - Total visible en agenda: {pendientes_count + en_curso_count}")

if __name__ == "__main__":
    check_agenda()