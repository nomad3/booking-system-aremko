#!/usr/bin/env python
"""
Script de diagnóstico: ¿Por qué solo veo 1 tarea urgente?

Verifica:
1. Zona horaria configurada
2. Tareas CRITICAL del usuario
3. Fechas de promise_due_at vs fecha actual
4. Reservas programadas para hoy
"""

import os
import sys
import django

# Configurar Django
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'booking_system.settings')
django.setup()

from control_gestion.models import Task, TimeCriticality, TaskState
from ventas.models import VentaReserva
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import datetime, timedelta


def main():
    print("=" * 80)
    print("🔍 DIAGNÓSTICO DE TAREAS URGENTES")
    print("=" * 80)
    print()

    # 1. ZONA HORARIA
    print("📅 ZONA HORARIA Y FECHA ACTUAL")
    print("-" * 80)
    now = timezone.now()
    print(f"Hora del servidor (UTC):     {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Hora en Chile (UTC-3):       {(now - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Fecha que usa la vista:      {now.date()}")
    print(f"Fecha real en Chile:         {(now - timedelta(hours=3)).date()}")
    print()

    # Detectar usuario OPERACIONES (Ernesto)
    try:
        ernesto = User.objects.filter(groups__name="OPERACIONES").first()
        if not ernesto:
            ernesto = User.objects.filter(username__icontains="ernesto").first()
        if not ernesto:
            print("⚠️  Usuario 'Ernesto' no encontrado")
            return
    except Exception as e:
        print(f"❌ Error buscando usuario: {e}")
        return

    print(f"👤 Usuario analizado: {ernesto.username} (ID: {ernesto.id})")
    print()

    # 2. TAREAS CRITICAL DEL USUARIO
    print("⏰ TAREAS CRITICAL (URGENTES)")
    print("-" * 80)

    tareas_critical_todas = Task.objects.filter(
        owner=ernesto,
        time_criticality=TimeCriticality.CRITICAL
    ).exclude(state=TaskState.DONE).order_by('promise_due_at')

    print(f"Total tareas CRITICAL no completadas: {tareas_critical_todas.count()}")
    print()

    if tareas_critical_todas.count() == 0:
        print("⚠️  No hay tareas CRITICAL asignadas a este usuario")
        print("   Esto puede significar:")
        print("   - No hay servicios programados para hoy/mañana")
        print("   - Los Cron Jobs no están ejecutándose")
        print("   - Las tareas se asignaron a otro usuario")
    else:
        # Agrupar por fecha
        today_server = now.date()
        today_chile = (now - timedelta(hours=3)).date()

        for tarea in tareas_critical_todas[:20]:  # Mostrar hasta 20
            fecha_tarea = tarea.promise_due_at.date() if tarea.promise_due_at else None
            hora_tarea = tarea.promise_due_at.strftime('%H:%M') if tarea.promise_due_at else 'Sin hora'

            # Determinar si es de hoy según servidor o Chile
            marca = ""
            if fecha_tarea == today_server:
                marca = "📅 HOY (servidor)"
            elif fecha_tarea == today_chile:
                marca = "🇨🇱 HOY (Chile)"
            elif fecha_tarea and fecha_tarea > today_server:
                marca = "📆 FUTURO"
            elif fecha_tarea and fecha_tarea < today_server:
                marca = "📁 PASADO"

            print(f"{marca:20} | {fecha_tarea} {hora_tarea:5} | ID:{tarea.id:4} | {tarea.title[:60]}")

    print()

    # 3. TAREAS FLEXIBLE
    print("🔵 TAREAS FLEXIBLE (SIN HORA ESPECÍFICA)")
    print("-" * 80)

    tareas_flexible = Task.objects.filter(
        owner=ernesto,
        time_criticality=TimeCriticality.FLEXIBLE
    ).exclude(state=TaskState.DONE).count()

    print(f"Total tareas FLEXIBLE: {tareas_flexible}")
    print()

    # 4. RESERVAS ACTIVAS
    print("📋 RESERVAS ACTIVAS (PENDIENTE/CHECKIN)")
    print("-" * 80)

    reservas_activas = VentaReserva.objects.filter(
        estado_reserva__in=['pendiente', 'checkin']
    ).prefetch_related('reservaservicios__servicio')

    print(f"Total reservas activas: {reservas_activas.count()}")
    print()

    if reservas_activas.count() > 0:
        print("Servicios programados:")
        for reserva in reservas_activas[:10]:  # Mostrar hasta 10
            for rs in reserva.reservaservicios.all():
                if rs.servicio and rs.servicio.nombre != "Descuento_Servicios":
                    fecha_servicio = rs.fecha_agendamiento
                    hora_servicio = rs.hora_inicio

                    marca = ""
                    if fecha_servicio == today_server:
                        marca = "📅 HOY (servidor)"
                    elif fecha_servicio == today_chile:
                        marca = "🇨🇱 HOY (Chile)"
                    elif fecha_servicio > today_server:
                        marca = "📆 FUTURO"

                    print(f"{marca:20} | {fecha_servicio} {hora_servicio:5} | Reserva #{reserva.id:4} | {rs.servicio.nombre}")
    else:
        print("⚠️  No hay reservas activas")
        print("   Esto explica por qué no se generan tareas urgentes")

    print()

    # 5. CONFIGURACIÓN TIME_ZONE
    print("⚙️  CONFIGURACIÓN DE DJANGO")
    print("-" * 80)
    from django.conf import settings
    print(f"TIME_ZONE: {settings.TIME_ZONE}")
    print(f"USE_TZ: {settings.USE_TZ}")
    print()

    # 6. RESUMEN
    print("=" * 80)
    print("📊 RESUMEN")
    print("=" * 80)
    print(f"✅ Tareas CRITICAL encontradas: {tareas_critical_todas.count()}")
    print(f"✅ Tareas FLEXIBLE encontradas: {tareas_flexible}")
    print(f"✅ Reservas activas: {reservas_activas.count()}")
    print()

    if now.date() != (now - timedelta(hours=3)).date():
        print("⚠️  PROBLEMA DE ZONA HORARIA DETECTADO:")
        print(f"   - Servidor dice que hoy es: {now.date()} (UTC)")
        print(f"   - En Chile hoy es:          {(now - timedelta(hours=3)).date()}")
        print(f"   - La vista filtra tareas con fecha: {now.date()}")
        print()
        print("💡 SOLUCIÓN:")
        print("   Verificar que TIME_ZONE en settings.py esté configurado como 'America/Santiago'")
        print("   O ajustar la lógica de la vista para usar timezone.localtime()")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
