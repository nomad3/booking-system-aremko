"""
Comando: Generar tareas de atención a clientes en servicio (20 min después del check-in)

Este comando detecta cuándo atender a clientes que ya hicieron check-in:
- 20 minutos después del inicio del servicio (hora agendada)
- SOLO para servicios de TINAS y CABAÑAS
- NO para masajes ni otros servicios
- Solo para reservas en estado 'checkin'

Lógica:
1. Buscar reservas en estado 'checkin'
2. Buscar servicios de TINAS o CABAÑAS dentro de esas reservas
3. Verificar si ya pasaron 20 minutos desde la hora de inicio del servicio
4. Si SÍ → Crear tarea de atención
5. Si NO → Esperar

Uso:
    python manage.py gen_atencion_clientes
    python manage.py gen_atencion_clientes --dry-run

Cron recomendado (cada 15 minutos):
    */15 * * * * python manage.py gen_atencion_clientes
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
    help = "Genera tareas de atención a clientes 20 min después del check-in (tinas y cabañas)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--tiempo-despues-checkin',
            type=int,
            default=20,
            help='Minutos después del inicio del servicio para crear tarea (default: 20)'
        )
        parser.add_argument(
            '--ventana',
            type=int,
            default=10,
            help='Ventana de tolerancia en minutos (default: 10, detecta entre 15-25 min)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular sin crear tareas'
        )

    def handle(self, *args, **options):
        tiempo_despues = options['tiempo_despues_checkin']  # 20 minutos
        ventana = options['ventana']  # ±5 minutos
        dry_run = options['dry_run']

        now = timezone.now()

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("👥 GENERACIÓN DE TAREAS DE ATENCIÓN A CLIENTES"))
        self.stdout.write("=" * 80 + "\n")

        self.stdout.write(f"🕐 Hora actual: {now.strftime('%H:%M')}")
        self.stdout.write(f"📅 Fecha: {now.date()}")
        self.stdout.write(f"⏱️  Tiempo después del check-in: {tiempo_despues} minutos")
        self.stdout.write(f"⏱️  Ventana de detección: ±{ventana} minutos\n")

        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  MODO DRY-RUN\n"))

        # Obtener usuario responsable (usando configuración o fallback)
        from control_gestion.models import TaskOwnerConfig

        responsable = TaskOwnerConfig.obtener_responsable_por_tipo('atencion_clientes')
        if not responsable:
            # Fallback: grupo VENTAS
            responsable = User.objects.filter(groups__name="VENTAS").first()
            if not responsable:
                responsable = User.objects.first()
                self.stdout.write(self.style.WARNING(
                    "⚠️  Grupo VENTAS no encontrado y sin configuración TaskOwnerConfig, usando primer usuario"
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    "ℹ️  Sin configuración TaskOwnerConfig, usando grupo VENTAS (fallback)"
                ))
        else:
            self.stdout.write(
                f"✅ Usando responsable configurado: {responsable.username}"
            )

        # IMPORTANTE: Solo buscar reservas que YA hicieron check-in
        # Usar solo servicios del DÍA ACTUAL
        today = now.date()

        self.stdout.write(f"🔍 Buscando reservas con check-in del día: {today}\n")

        reservas_checkin = VentaReserva.objects.filter(
            estado_reserva='checkin'  # Solo reservas que ya hicieron check-in
        ).prefetch_related('reservaservicios__servicio')

        servicios_revisados = 0
        tareas_creadas = 0
        servicios_fuera_ventana = 0
        servicios_tipo_invalido = 0
        errores = 0

        for reserva in reservas_checkin:
            for rs in reserva.reservaservicios.all():
                # FILTRO 1: Excluir "Descuento_Servicios"
                if rs.servicio and rs.servicio.nombre == "Descuento_Servicios":
                    continue

                # FILTRO 2: Solo servicios de TINAS y CABAÑAS
                if not rs.servicio or rs.servicio.tipo_servicio not in ['tina', 'cabana']:
                    servicios_tipo_invalido += 1
                    continue

                try:
                    # Normalizar hora de inicio del servicio
                    hora_str = str(rs.hora_inicio).strip()
                    hora_str = hora_str.replace(';', ':').replace('.', ':')

                    if ':' not in hora_str:
                        if len(hora_str) == 4:
                            hora_str = f"{hora_str[:2]}:{hora_str[2:]}"
                        elif len(hora_str) == 2:
                            hora_str = f"{hora_str}:00"

                    hora_inicio = datetime.strptime(hora_str, "%H:%M").time()
                    datetime_inicio = timezone.make_aware(
                        datetime.combine(rs.fecha_agendamiento, hora_inicio)
                    )

                    # FILTRO CRÍTICO: Solo servicios del DÍA ACTUAL
                    if rs.fecha_agendamiento != today:
                        continue  # Servicio es de otro día, ignorar

                    # Calcular cuándo debe ejecutarse la tarea de atención
                    # (inicio del servicio + 20 minutos)
                    datetime_atencion = datetime_inicio + timedelta(minutes=tiempo_despues)

                    # Ventana de detección: ¿estamos en el momento correcto?
                    # Ej: Si ahora son las 10:25 y el servicio empezó a las 10:00
                    # → datetime_atencion = 10:20
                    # → diferencia = 10:25 - 10:20 = 5 minutos
                    # → SI está dentro de ventana (0-10 min) → crear tarea

                    minutos_desde_atencion = (now - datetime_atencion).total_seconds() / 60

                    # Si aún no es tiempo de atender (falta tiempo)
                    if minutos_desde_atencion < 0:
                        continue

                    # Si ya pasó mucho tiempo (más de ventana)
                    if minutos_desde_atencion > ventana:
                        servicios_fuera_ventana += 1
                        continue

                    # ✅ Estamos en la ventana correcta (0 a ventana minutos después)
                    servicios_revisados += 1
                    servicio_nombre = rs.servicio.nombre

                    # Verificar si ya existe tarea de atención para este servicio
                    tarea_existe = Task.objects.filter(
                        reservation_id=str(reserva.id),
                        title__icontains="Atención de clientes"
                    ).filter(
                        title__icontains=servicio_nombre
                    ).exists()

                    if tarea_existe:
                        self.stdout.write(
                            f"  ⏭️  {servicio_nombre} - Reserva #{reserva.id} - "
                            f"Tarea ya existe"
                        )
                        continue

                    # Crear tarea de atención
                    self.stdout.write(
                        f"  ✅ {servicio_nombre} - Reserva #{reserva.id}"
                    )
                    self.stdout.write(
                        f"     Inicio servicio: {datetime_inicio.strftime('%H:%M')}"
                    )
                    self.stdout.write(
                        f"     Tiempo para atención: {datetime_atencion.strftime('%H:%M')}"
                    )
                    self.stdout.write(
                        f"     Han pasado {int(minutos_desde_atencion)} min desde hora de atención → CREAR TAREA"
                    )

                    if not dry_run:
                        # Determinar swimlane según tipo de servicio
                        if rs.servicio.tipo_servicio == 'tina':
                            swimlane = Swimlane.ATENCION
                        elif rs.servicio.tipo_servicio == 'cabana':
                            swimlane = Swimlane.ATENCION
                        else:
                            swimlane = Swimlane.ATENCION

                        # Importar TimeCriticality
                        from control_gestion.models import TimeCriticality

                        Task.objects.create(
                            title=f"Atención de clientes – {servicio_nombre} (Reserva #{reserva.id})",
                            description=(
                                f"⏰ Cliente hizo check-in, servicio comenzó a las {datetime_inicio.strftime('%H:%M')}\\n\\n"
                                f"👥 ATENCIÓN AL CLIENTE ({datetime_atencion.strftime('%H:%M')} - 20 min después):\\n\\n"
                                f"✅ CHECKLIST DE ATENCIÓN:\\n"
                                f"• Acercarse al cliente y saludar\\n"
                                f"• Preguntar si está cómodo y si necesita algo\\n"
                                f"• Ofrecer bebidas (agua, té, café) si no se han ofrecido\\n"
                                f"• Ofrecer snacks o amenidades disponibles\\n"
                                f"• Verificar temperatura del agua (si es tina) - debe estar entre 36-38°C\\n"
                                f"• Preguntar si el espacio está a su gusto (música, luz, etc.)\\n"
                                f"• Resolver cualquier solicitud o necesidad\\n"
                                f"• Informar sobre tiempo restante si preguntan\\n"
                                f"• Recordar que pueden llamar si necesitan algo más\\n\\n"
                                f"🎯 OBJETIVO: Asegurar que el cliente tenga una experiencia excepcional\\n"
                                f"💡 TIP: Ser discreto y respetuoso, no interrumpir si están descansando\\n\\n"
                                f"📋 Cliente: {reserva.cliente.nombre if reserva.cliente else 'N/A'}\\n"
                                f"📅 Fecha: {rs.fecha_agendamiento}\\n"
                                f"🕐 Hora inicio: {rs.hora_inicio}"
                            ),
                            swimlane=swimlane,
                            owner=responsable,
                            created_by=responsable,
                            state=TaskState.BACKLOG,
                            queue_position=2,
                            reservation_id=str(reserva.id),
                            service_type=rs.servicio.tipo_servicio,
                            source=TaskSource.SISTEMA,
                            promise_due_at=datetime_atencion,
                            time_criticality=TimeCriticality.CRITICAL  # ⭐ CRÍTICA - Hora exacta
                        )
                        tareas_creadas += 1
                        self.stdout.write(self.style.SUCCESS("       → Tarea de atención creada"))
                    else:
                        self.stdout.write("       [DRY-RUN]")

                except Exception as e:
                    errores += 1
                    logger.error(f"Error procesando servicio {rs.id}: {str(e)}")
                    self.stdout.write(self.style.ERROR(
                        f"  ❌ Error en servicio #{rs.id}: {str(e)}"
                    ))

        # Resumen
        self.stdout.write("\\n" + "=" * 80)
        self.stdout.write(f"📊 Servicios revisados (en ventana): {servicios_revisados}")
        self.stdout.write(f"⏭️  Servicios fuera de ventana: {servicios_fuera_ventana}")
        self.stdout.write(f"🚫 Servicios excluidos (masajes u otros): {servicios_tipo_invalido}")
        self.stdout.write(f"✅ Tareas de atención creadas: {tareas_creadas}")
        if errores > 0:
            self.stdout.write(f"❌ Errores: {errores}")
        self.stdout.write("=" * 80 + "\\n")

        if not dry_run and tareas_creadas > 0:
            self.stdout.write(self.style.SUCCESS(
                f"✅ {tareas_creadas} tarea(s) de atención generadas"
            ))
        elif servicios_revisados == 0:
            self.stdout.write(self.style.WARNING(
                "ℹ️  No hay servicios en la ventana de tiempo para atender"
            ))

        # Configuración cron
        self.stdout.write("\\n" + self.style.WARNING("📌 CONFIGURACIÓN CRON:"))
        self.stdout.write("   Ejecutar cada 15 minutos:")
        self.stdout.write("   */15 * * * * python manage.py gen_atencion_clientes\\n")
