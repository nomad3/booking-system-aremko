"""
Comando: Generar tareas de preparación de servicios (1 hora antes)

Este comando debe ejecutarse CADA HORA para revisar qué servicios
comienzan en la próxima hora y crear tareas de preparación.

Ejemplo: Si hay servicio a las 16:00, a las 15:00 se crea la tarea
de preparar la tina/sala.

Uso:
    python manage.py gen_preparacion_servicios

Cron recomendado (cada hora):
    0 * * * * cd /path/to/proyecto && python manage.py gen_preparacion_servicios
    
    O cada 30 minutos para mayor precisión:
    */30 * * * * cd /path/to/proyecto && python manage.py gen_preparacion_servicios
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from control_gestion.models import Task, Swimlane, TaskState, TaskSource
from ventas.models import VentaReserva, ReservaServicio
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Genera tareas de preparación 1 hora antes del inicio de servicios"

    def add_arguments(self, parser):
        parser.add_argument(
            '--anticipacion',
            type=int,
            default=60,
            help='Minutos de anticipación para crear tarea (default: 60 = 1 hora antes)'
        )
        parser.add_argument(
            '--tolerancia',
            type=int,
            default=30,
            help='Tolerancia en minutos (default: 30, crea tarea si servicio está entre 60-90 min)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular sin crear tareas'
        )

    def handle(self, *args, **options):
        anticipacion = options['anticipacion']  # Ej: 60 minutos
        tolerancia = options['tolerancia']      # Ej: 30 minutos
        dry_run = options['dry_run']
        
        now = timezone.now()
        
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("🔔 GENERACIÓN DE TAREAS DE PREPARACIÓN"))
        self.stdout.write("=" * 80 + "\n")
        
        self.stdout.write(f"🕐 Hora actual: {now.strftime('%H:%M')}")
        self.stdout.write(f"📅 Fecha: {now.date()}")
        self.stdout.write(f"⏱️  Anticipación: {anticipacion} minutos antes del servicio")
        self.stdout.write(f"⏱️  Tolerancia: ±{tolerancia} minutos\n")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  MODO DRY-RUN\n"))
        
        # Calcular rango de tiempo para detectar servicios
        # Queremos crear la tarea cuando el servicio esté entre:
        # (anticipacion - tolerancia) y (anticipacion + tolerancia) minutos en el futuro
        #
        # Ejemplo con anticipacion=60, tolerancia=30:
        # - Si ahora son las 14:00
        # - Detectar servicios entre 15:00 (14:00 + 60min) y 15:30 (14:00 + 90min)
        # - Esto cubre servicios a las 15:00, 15:15, 15:30
        
        min_minutos_futuro = anticipacion - tolerancia  # Ej: 60 - 30 = 30 min
        max_minutos_futuro = anticipacion + tolerancia  # Ej: 60 + 30 = 90 min
        
        inicio_ventana = now + timedelta(minutes=min_minutos_futuro)
        fin_ventana = now + timedelta(minutes=max_minutos_futuro)
        
        self.stdout.write(
            f"🔍 Buscando servicios que comiencen entre "
            f"{inicio_ventana.strftime('%H:%M')} y {fin_ventana.strftime('%H:%M')}..."
        )
        self.stdout.write(
            f"   (Esto cubre servicios con horarios como: "
            f"{inicio_ventana.strftime('%H:%M')}, {(inicio_ventana + timedelta(minutes=15)).strftime('%H:%M')}, "
            f"{(inicio_ventana + timedelta(minutes=30)).strftime('%H:%M')}, etc.)\n"
        )
        
        # Obtener usuario de operaciones
        ops_user = User.objects.filter(groups__name="OPERACIONES").first()
        if not ops_user:
            ops_user = User.objects.first()
            self.stdout.write(self.style.WARNING(
                "⚠️  Grupo OPERACIONES no encontrado, usando primer usuario"
            ))
        
        # Buscar reservas con check-in hecho (estado checkin o checkout)
        reservas_activas = VentaReserva.objects.filter(
            estado_reserva__in=['checkin', 'checkout']
        ).prefetch_related('reservaservicios__servicio')
        
        servicios_encontrados = 0
        tareas_creadas = 0
        tareas_ya_existen = 0
        
        for reserva in reservas_activas:
            for rs in reserva.reservaservicios.all():
                # Construir datetime del servicio
                try:
                    hora_servicio = datetime.strptime(rs.hora_inicio, "%H:%M").time()
                    datetime_servicio = timezone.make_aware(
                        datetime.combine(rs.fecha_agendamiento, hora_servicio)
                    )
                    
                    # Calcular cuándo preparar (1 hora antes)
                    hora_preparacion = datetime_servicio - timedelta(hours=1)
                    
                    # Si el servicio está en nuestra ventana de tiempo
                    # (servicios que empiezan en la próxima hora)
                    if inicio_ventana <= datetime_servicio <= fin_ventana:
                        servicios_encontrados += 1
                        
                        servicio_nombre = rs.servicio.nombre if rs.servicio else "Servicio"
                        
                        # Verificar si ya existe una tarea de preparación para este servicio
                        tarea_existe = Task.objects.filter(
                            reservation_id=str(reserva.id),
                            title__icontains=f"Preparar servicio",
                            title__icontains=servicio_nombre
                        ).exists()
                        
                        if tarea_existe:
                            tareas_ya_existen += 1
                            self.stdout.write(
                                f"  ⏭️  {servicio_nombre} (Reserva #{reserva.id}) - "
                                f"Tarea ya existe"
                            )
                            continue
                        
                        # Obtener tramo del cliente (opcional)
                        segment_tag = ""
                        try:
                            from ventas.services.tramo_service import TramoService
                            gasto_total = TramoService.calcular_gasto_cliente(reserva.cliente)
                            tramo_actual = TramoService.calcular_tramo(float(gasto_total))
                            segment_tag = f"Tramo {tramo_actual}"
                        except Exception:
                            pass
                        
                        # Obtener teléfono (últimos 9 dígitos)
                        telefono = getattr(reserva.cliente, 'telefono', '') if reserva.cliente else ''
                        digits = "".join([c for c in str(telefono) if c.isdigit()])
                        customer_phone = digits[-9:] if len(digits) >= 9 else digits
                        
                        self.stdout.write(
                            f"  ✅ {servicio_nombre} - Hora servicio: {rs.hora_inicio} - "
                            f"Reserva #{reserva.id}"
                        )
                        self.stdout.write(
                            f"     Preparar a las: {hora_preparacion.strftime('%H:%M')}"
                        )
                        
                        if not dry_run:
                            # Crear tarea de preparación
                            Task.objects.create(
                                title=f"Preparar servicio – {servicio_nombre} (Reserva #{reserva.id})",
                                description=(
                                    f"⏰ SERVICIO COMIENZA A LAS {rs.hora_inicio}\n"
                                    f"📅 Fecha: {rs.fecha_agendamiento}\n"
                                    f"👤 Cliente: {reserva.cliente.nombre if reserva.cliente else 'N/A'}\n\n"
                                    f"🔧 TAREAS DE PREPARACIÓN (completar 1 hora antes):\n"
                                    f"• Limpiar y sanitizar tina/sala\n"
                                    f"• Llenar tina con agua caliente\n"
                                    f"• Verificar temperatura (36-38°C)\n"
                                    f"• Preparar toallas y amenidades\n"
                                    f"• Verificar que todo funcione correctamente\n"
                                    f"• Área lista y presentable para las {rs.hora_inicio}"
                                ),
                                swimlane=Swimlane.OPERACION,
                                owner=ops_user,
                                created_by=ops_user,
                                state=TaskState.BACKLOG,
                                queue_position=1,
                                reservation_id=str(reserva.id),
                                customer_phone_last9=customer_phone,
                                segment_tag=segment_tag,
                                service_type=rs.servicio.tipo_servicio if rs.servicio else '',
                                source=TaskSource.SISTEMA,
                                promise_due_at=hora_preparacion  # ⭐ 1 hora antes del servicio
                            )
                            tareas_creadas += 1
                            self.stdout.write(self.style.SUCCESS("       → Tarea creada"))
                        else:
                            self.stdout.write("       [DRY-RUN]")
                
                except Exception as e:
                    logger.error(f"Error procesando servicio de reserva {reserva.id}: {str(e)}")
                    self.stdout.write(self.style.ERROR(
                        f"  ❌ Error en reserva #{reserva.id}: {str(e)}"
                    ))
        
        # Resumen
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(f"📊 Servicios en ventana: {servicios_encontrados}")
        self.stdout.write(f"✅ Tareas creadas: {tareas_creadas}")
        self.stdout.write(f"⏭️  Tareas ya existían: {tareas_ya_existen}")
        self.stdout.write("=" * 80 + "\n")
        
        if not dry_run and tareas_creadas > 0:
            self.stdout.write(self.style.SUCCESS(
                f"✅ {tareas_creadas} tarea(s) de preparación generadas"
            ))
        elif servicios_encontrados == 0:
            self.stdout.write(self.style.WARNING(
                "ℹ️  No hay servicios próximos en la ventana de tiempo"
            ))
        
        # Nota de configuración
        self.stdout.write("\n" + self.style.WARNING("📌 CONFIGURACIÓN CRON:"))
        self.stdout.write("   ⭐ RECOMENDADO: Ejecutar cada 30 minutos:")
        self.stdout.write("   */30 * * * * python manage.py gen_preparacion_servicios")
        self.stdout.write("\n   Esto cubre servicios con horarios intermedios (14:30, 15:15, etc.)")
        self.stdout.write("\n   También puedes ejecutar cada hora si prefieres:")
        self.stdout.write("   0 * * * * python manage.py gen_preparacion_servicios\n")

