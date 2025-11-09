"""
Comando de diagnóstico: Verificar por qué no se generan tareas automáticas

Uso:
    python manage.py diagnostico_tareas
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User, Group
from datetime import datetime, timedelta
from control_gestion.models import Task, Swimlane, TaskState
from ventas.models import VentaReserva, ReservaServicio
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Diagnóstico completo del sistema de generación de tareas"

    def handle(self, *args, **options):
        now = timezone.now()

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("🔍 DIAGNÓSTICO DEL SISTEMA DE TAREAS AUTOMÁTICAS"))
        self.stdout.write("=" * 80 + "\n")

        self.stdout.write(f"🕐 Hora actual: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdout.write(f"🌍 Timezone: {timezone.get_current_timezone()}\n")

        # ============================================================
        # 1. VERIFICAR GRUPOS DE USUARIOS
        # ============================================================
        self.stdout.write(self.style.SUCCESS("\n1️⃣ GRUPOS DE USUARIOS"))
        self.stdout.write("-" * 80)

        grupos = ['OPERACIONES', 'RECEPCION', 'SUPERVISION']
        for grupo_name in grupos:
            try:
                grupo = Group.objects.get(name=grupo_name)
                usuarios = User.objects.filter(groups=grupo)
                count = usuarios.count()

                if count > 0:
                    self.stdout.write(f"✅ Grupo '{grupo_name}': {count} usuario(s)")
                    for user in usuarios:
                        self.stdout.write(f"   - {user.username} ({user.email})")
                else:
                    self.stdout.write(self.style.WARNING(
                        f"⚠️  Grupo '{grupo_name}': Existe pero SIN usuarios"
                    ))
            except Group.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"❌ Grupo '{grupo_name}': NO EXISTE"
                ))
                self.stdout.write(f"   → Crear con: Group.objects.create(name='{grupo_name}')")

        # Verificar usuario de operaciones
        ops_user = User.objects.filter(groups__name="OPERACIONES").first()
        if ops_user:
            self.stdout.write(f"\n✅ Usuario de operaciones encontrado: {ops_user.username}")
        else:
            self.stdout.write(self.style.ERROR(
                "\n❌ NO hay usuario en grupo OPERACIONES"
            ))
            self.stdout.write("   → Las tareas se asignarán al primer usuario del sistema")
            primer_usuario = User.objects.first()
            if primer_usuario:
                self.stdout.write(f"   → Primer usuario: {primer_usuario.username}")

        # ============================================================
        # 2. VERIFICAR RESERVAS DE HOY
        # ============================================================
        self.stdout.write(self.style.SUCCESS("\n2️⃣ RESERVAS DEL DÍA DE HOY"))
        self.stdout.write("-" * 80)

        hoy = now.date()

        # Reservas de hoy
        reservas_hoy = VentaReserva.objects.filter(
            fecha_agendamiento=hoy
        ).order_by('fecha_agendamiento')

        self.stdout.write(f"📅 Fecha buscada: {hoy}")
        self.stdout.write(f"📊 Total reservas hoy: {reservas_hoy.count()}\n")

        if reservas_hoy.count() == 0:
            self.stdout.write(self.style.WARNING(
                "⚠️  NO HAY RESERVAS PARA HOY"
            ))
            self.stdout.write("   → Buscar reservas en otros días...\n")

            # Buscar en rango de ±3 días
            for delta in [-3, -2, -1, 1, 2, 3]:
                fecha = hoy + timedelta(days=delta)
                count = VentaReserva.objects.filter(fecha_agendamiento=fecha).count()
                if count > 0:
                    self.stdout.write(f"   {fecha}: {count} reserva(s)")
        else:
            self.stdout.write(f"✅ Reservas encontradas para hoy ({hoy}):\n")

            for reserva in reservas_hoy:
                self.stdout.write(
                    f"   Reserva #{reserva.id} - "
                    f"Estado: {reserva.estado_reserva} - "
                    f"Cliente: {reserva.cliente.nombre if reserva.cliente else 'N/A'}"
                )

                # Servicios de la reserva
                servicios = reserva.reservaservicios.all()
                if servicios.exists():
                    for rs in servicios:
                        hora = rs.hora_inicio
                        servicio_nombre = rs.servicio.nombre if rs.servicio else "Servicio desconocido"

                        # Calcular si está en ventana de preparación
                        try:
                            hora_str = str(hora).strip().replace(';', ':').replace('.', ':')
                            if ':' not in hora_str:
                                if len(hora_str) == 4:
                                    hora_str = f"{hora_str[:2]}:{hora_str[2:]}"

                            hora_servicio = datetime.strptime(hora_str, "%H:%M").time()
                            datetime_servicio = timezone.make_aware(
                                datetime.combine(hoy, hora_servicio)
                            )

                            # Calcular si debería tener tarea
                            hora_preparacion = datetime_servicio - timedelta(hours=1)

                            if now >= hora_preparacion:
                                estado_tarea = "⏰ Ya debería existir tarea"
                            else:
                                minutos_faltantes = int((hora_preparacion - now).total_seconds() / 60)
                                estado_tarea = f"⏳ Tarea en {minutos_faltantes} minutos"

                            self.stdout.write(
                                f"      → {servicio_nombre} a las {hora} - {estado_tarea}"
                            )
                        except Exception as e:
                            self.stdout.write(
                                f"      → {servicio_nombre} a las {hora} - ❌ Error: {str(e)}"
                            )
                else:
                    self.stdout.write("      (Sin servicios específicos)")

        # ============================================================
        # 3. VERIFICAR TAREAS CREADAS HOY
        # ============================================================
        self.stdout.write(self.style.SUCCESS("\n3️⃣ TAREAS CREADAS HOY"))
        self.stdout.write("-" * 80)

        tareas_hoy = Task.objects.filter(
            created_at__date=hoy,
            source='SISTEMA'
        ).order_by('-created_at')

        self.stdout.write(f"📊 Total tareas del sistema hoy: {tareas_hoy.count()}\n")

        if tareas_hoy.count() == 0:
            self.stdout.write(self.style.WARNING(
                "⚠️  NO SE HAN CREADO TAREAS AUTOMÁTICAS HOY"
            ))
        else:
            for tarea in tareas_hoy[:10]:  # Mostrar últimas 10
                self.stdout.write(
                    f"   ✅ {tarea.title} - "
                    f"Estado: {tarea.get_state_display()} - "
                    f"Creada: {tarea.created_at.strftime('%H:%M')}"
                )

        # Tareas de preparación específicamente
        tareas_preparacion = Task.objects.filter(
            created_at__date=hoy,
            title__icontains="Preparar servicio"
        )

        self.stdout.write(f"\n📊 Tareas de preparación hoy: {tareas_preparacion.count()}")

        # ============================================================
        # 4. VERIFICAR VENTANA DE TIEMPO ACTUAL
        # ============================================================
        self.stdout.write(self.style.SUCCESS("\n4️⃣ VENTANA DE TIEMPO PARA GENERACIÓN"))
        self.stdout.write("-" * 80)

        # Usar misma lógica que gen_preparacion_servicios.py
        anticipacion = 60  # 1 hora
        tolerancia = 20    # ±20 minutos

        min_minutos_futuro = anticipacion - tolerancia  # 40 min
        max_minutos_futuro = anticipacion + tolerancia  # 80 min

        inicio_ventana = now + timedelta(minutes=min_minutos_futuro)
        fin_ventana = now + timedelta(minutes=max_minutos_futuro)

        self.stdout.write(f"⏱️  Anticipación: {anticipacion} minutos")
        self.stdout.write(f"⏱️  Tolerancia: ±{tolerancia} minutos")
        self.stdout.write(
            f"🔍 Ventana actual: {inicio_ventana.strftime('%H:%M')} - {fin_ventana.strftime('%H:%M')}"
        )
        self.stdout.write(
            f"   (Buscando servicios que comiencen en este rango)\n"
        )

        # Buscar servicios en ventana
        servicios_en_ventana = 0
        reservas_activas = VentaReserva.objects.filter(
            estado_reserva__in=['pendiente', 'checkin', 'checkout']
        ).prefetch_related('reservaservicios__servicio')

        for reserva in reservas_activas:
            for rs in reserva.reservaservicios.all():
                try:
                    hora_str = str(rs.hora_inicio).strip().replace(';', ':').replace('.', ':')
                    if ':' not in hora_str and len(hora_str) == 4:
                        hora_str = f"{hora_str[:2]}:{hora_str[2:]}"

                    hora_servicio = datetime.strptime(hora_str, "%H:%M").time()
                    datetime_servicio = timezone.make_aware(
                        datetime.combine(rs.fecha_agendamiento, hora_servicio)
                    )

                    if inicio_ventana <= datetime_servicio <= fin_ventana:
                        servicios_en_ventana += 1
                        servicio_nombre = rs.servicio.nombre if rs.servicio else "Servicio"

                        # Verificar si existe tarea
                        tarea_existe = Task.objects.filter(
                            reservation_id=str(reserva.id),
                            title__icontains="Preparar servicio"
                        ).exists()

                        estado = "✅ Tarea ya existe" if tarea_existe else "❌ Tarea NO existe (debería crearse)"

                        self.stdout.write(
                            f"   🎯 {servicio_nombre} a las {rs.hora_inicio} "
                            f"(Reserva #{reserva.id}) - {estado}"
                        )
                except Exception:
                    pass

        if servicios_en_ventana == 0:
            self.stdout.write("   ℹ️  No hay servicios en la ventana de tiempo actual")

        # ============================================================
        # 5. VERIFICAR CONFIGURACIÓN DE CRON
        # ============================================================
        self.stdout.write(self.style.SUCCESS("\n5️⃣ CONFIGURACIÓN DE CRON EN RENDER"))
        self.stdout.write("-" * 80)

        self.stdout.write(self.style.WARNING(
            "⚠️  No se puede verificar automáticamente desde aquí."
        ))
        self.stdout.write("\n📌 PASOS PARA VERIFICAR EN RENDER:")
        self.stdout.write("   1. Ir a: https://dashboard.render.com")
        self.stdout.write("   2. Buscar: 'Cron Jobs' en el proyecto")
        self.stdout.write("   3. Verificar que exista cron job con:")
        self.stdout.write("      - Comando: python manage.py gen_preparacion_servicios")
        self.stdout.write("      - Schedule: */15 * * * * (cada 15 minutos)")
        self.stdout.write("      - Estado: Enabled/Running\n")

        self.stdout.write(self.style.WARNING("📌 SI NO EXISTE EL CRON JOB:"))
        self.stdout.write("   1. Crear nuevo Cron Job en Render")
        self.stdout.write("   2. Nombre: 'Generar Tareas de Preparación'")
        self.stdout.write("   3. Comando: python manage.py gen_preparacion_servicios")
        self.stdout.write("   4. Schedule: */15 * * * *")
        self.stdout.write("   5. Environment: Same as web service")

        # ============================================================
        # 6. RESUMEN Y RECOMENDACIONES
        # ============================================================
        self.stdout.write(self.style.SUCCESS("\n6️⃣ RESUMEN Y RECOMENDACIONES"))
        self.stdout.write("=" * 80 + "\n")

        # Análisis
        tiene_grupo_ops = Group.objects.filter(name="OPERACIONES").exists()
        tiene_usuario_ops = User.objects.filter(groups__name="OPERACIONES").exists()
        tiene_reservas_hoy = reservas_hoy.count() > 0
        tiene_tareas_hoy = tareas_hoy.count() > 0

        problemas = []

        if not tiene_grupo_ops:
            problemas.append("❌ Grupo 'OPERACIONES' no existe")
            self.stdout.write(self.style.ERROR("   Solución: Group.objects.create(name='OPERACIONES')"))

        if not tiene_usuario_ops:
            problemas.append("❌ No hay usuarios en grupo OPERACIONES")
            self.stdout.write(self.style.ERROR(
                "   Solución: Asignar usuario al grupo en Admin > Users > Grupos"
            ))

        if not tiene_reservas_hoy:
            problemas.append("⚠️  No hay reservas para hoy")
            self.stdout.write(self.style.WARNING(
                "   Esto es normal si no hay clientes agendados"
            ))

        if tiene_reservas_hoy and not tiene_tareas_hoy:
            problemas.append("❌ HAY RESERVAS pero NO se han generado tareas")
            self.stdout.write(self.style.ERROR(
                "   Solución: Verificar que Cron Job esté configurado en Render"
            ))
            self.stdout.write(self.style.ERROR(
                "   O ejecutar manualmente: python manage.py gen_preparacion_servicios"
            ))

        if not problemas:
            self.stdout.write(self.style.SUCCESS(
                "✅ No se detectaron problemas de configuración"
            ))
        else:
            self.stdout.write(self.style.ERROR(f"\n🚨 {len(problemas)} PROBLEMA(S) DETECTADO(S):\n"))
            for p in problemas:
                self.stdout.write(f"   {p}")

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("✅ DIAGNÓSTICO COMPLETADO"))
        self.stdout.write("=" * 80 + "\n")
