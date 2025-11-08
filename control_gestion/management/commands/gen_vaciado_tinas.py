"""
Comando: Generar tareas de vaciado de tinas (120 min después del check-in)

Este comando detecta cuándo una tina debe vaciarse:
- 120 minutos (2 horas) después del inicio del servicio
- SOLO si NO hay otro servicio inmediatamente después en esa tina

Lógica:
1. Buscar servicios de TINAS que terminaron hace poco
2. Verificar si hay otro servicio en la misma tina después
3. Si NO hay → Crear tarea de vaciado
4. Si SÍ hay → NO vaciar (sigue llena para el siguiente)

Uso:
    python manage.py gen_vaciado_tinas
    python manage.py gen_vaciado_tinas --dry-run

Cron recomendado (cada 30 minutos):
    */30 * * * * python manage.py gen_vaciado_tinas
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
    help = "Genera tareas de vaciado de tinas 2h después si no hay servicio siguiente"

    def add_arguments(self, parser):
        parser.add_argument(
            '--duracion-tina',
            type=int,
            default=120,
            help='Duración del servicio de tina en minutos (default: 120)'
        )
        parser.add_argument(
            '--ventana',
            type=int,
            default=150,
            help='Ventana de tiempo para buscar servicios terminados (default: 150 min)'
        )
        parser.add_argument(
            '--gap-minimo',
            type=int,
            default=30,
            help='Gap mínimo entre servicios para considerar vaciar (default: 30 min)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular sin crear tareas'
        )

    def handle(self, *args, **options):
        duracion_tina = options['duracion_tina']
        ventana = options['ventana']
        gap_minimo = options['gap_minimo']
        dry_run = options['dry_run']
        
        now = timezone.now()
        
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("💧 GENERACIÓN DE TAREAS DE VACIADO DE TINAS"))
        self.stdout.write("=" * 80 + "\n")
        
        self.stdout.write(f"🕐 Hora actual: {now.strftime('%H:%M')}")
        self.stdout.write(f"📅 Fecha: {now.date()}")
        self.stdout.write(f"⏱️  Duración tina: {duracion_tina} minutos")
        self.stdout.write(f"⏱️  Ventana búsqueda: últimos {ventana} minutos")
        self.stdout.write(f"⏱️  Gap mínimo entre servicios: {gap_minimo} minutos\n")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  MODO DRY-RUN\n"))
        
        # Obtener usuario de operaciones
        ops_user = User.objects.filter(groups__name="OPERACIONES").first()
        if not ops_user:
            ops_user = User.objects.first()
        
        # Buscar servicios de TINAS que ya terminaron (reserva en checkin o checkout)
        # Buscar en ventana de tiempo (ej: últimas 2.5 horas)
        inicio_busqueda = now - timedelta(minutes=ventana)
        
        # Buscar reservas de TINAS activas
        reservas = VentaReserva.objects.filter(
            estado_reserva__in=['checkin', 'checkout']
        ).prefetch_related('reservaservicios__servicio')
        
        servicios_revisados = 0
        tareas_creadas = 0
        servicios_con_siguiente = 0
        errores = 0
        
        for reserva in reservas:
            for rs in reserva.reservaservicios.all():
                # Solo servicios de TINAS
                if not rs.servicio or rs.servicio.tipo_servicio != 'tina':
                    continue
                
                try:
                    # Normalizar hora
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
                    
                    # Calcular hora de fin del servicio (inicio + duración)
                    datetime_fin = datetime_inicio + timedelta(minutes=duracion_tina)
                    
                    # ¿Ya pasó el tiempo de vaciado? (ahora >= fin del servicio)
                    if now < datetime_fin:
                        continue  # Servicio aún no termina
                    
                    # ¿Está dentro de la ventana de búsqueda?
                    if now > datetime_fin + timedelta(minutes=ventana):
                        continue  # Ya pasó hace mucho, probablemente ya se vació
                    
                    servicios_revisados += 1
                    servicio_nombre = rs.servicio.nombre
                    
                    # LÓGICA CRÍTICA: ¿Hay otro servicio de TINA después en la misma tina?
                    # Necesitamos identificar cuál tina es (por nombre del servicio)
                    
                    # Buscar en el nombre del servicio qué tina es
                    # Ejemplos: "Tina Hornopiren", "Tina Puntiagudo", etc.
                    tina_id = None
                    nombre_lower = servicio_nombre.lower()
                    
                    # Mapeo de nombres a IDs de tina
                    tinas_map = {
                        'hornopiren': 'TINA_1',
                        'puntiagudo': 'TINA_2',
                        'villarrica': 'TINA_3',
                        'osorno': 'TINA_4',
                        'calbuco': 'TINA_5',
                        'llanquihue': 'TINA_6',
                        'lonquimay': 'TINA_7',
                        'antillanca': 'TINA_8',
                    }
                    
                    for nombre_tina, tina_ref in tinas_map.items():
                        if nombre_tina in nombre_lower:
                            tina_id = tina_ref
                            break
                    
                    if not tina_id:
                        # Si no se puede identificar la tina, crear tarea de todas formas
                        tina_id = servicio_nombre
                    
                    # Buscar si hay otro servicio de TINA después en las próximas 3 horas
                    servicios_siguientes = ReservaServicio.objects.filter(
                        servicio__tipo_servicio='tina',
                        servicio__nombre__icontains=servicio_nombre.split()[-1],  # Ej: "Hornopiren"
                        fecha_agendamiento=rs.fecha_agendamiento
                    ).exclude(id=rs.id)
                    
                    # Verificar si hay servicio que empieza dentro de gap_minimo después
                    hay_siguiente = False
                    for srv_sig in servicios_siguientes:
                        try:
                            hora_sig_str = str(srv_sig.hora_inicio).strip().replace(';', ':').replace('.', ':')
                            if ':' not in hora_sig_str and len(hora_sig_str) == 4:
                                hora_sig_str = f"{hora_sig_str[:2]}:{hora_sig_str[2:]}"
                            
                            hora_sig = datetime.strptime(hora_sig_str, "%H:%M").time()
                            datetime_sig = timezone.make_aware(
                                datetime.combine(srv_sig.fecha_agendamiento, hora_sig)
                            )
                            
                            # Si el siguiente servicio empieza dentro del gap mínimo
                            diferencia_min = (datetime_sig - datetime_fin).total_seconds() / 60
                            
                            if 0 <= diferencia_min <= gap_minimo:
                                hay_siguiente = True
                                self.stdout.write(
                                    f"  ⏭️  {servicio_nombre} - Reserva #{reserva.id} - "
                                    f"HAY servicio siguiente a las {hora_sig_str} "
                                    f"(gap: {int(diferencia_min)} min) - NO vaciar"
                                )
                                servicios_con_siguiente += 1
                                break
                        except Exception:
                            continue
                    
                    if hay_siguiente:
                        continue
                    
                    # NO hay servicio siguiente → VACIAR
                    # Verificar si ya existe tarea de vaciado
                    nombre_tina_corto = servicio_nombre.split()[-1]  # Ej: "Hornopiren"
                    tarea_existe = Task.objects.filter(
                        reservation_id=str(reserva.id),
                        title__icontains="Vaciar",
                        title__icontains=nombre_tina_corto
                    ).exists()
                    
                    if tarea_existe:
                        self.stdout.write(
                            f"  ⏭️  {servicio_nombre} - Reserva #{reserva.id} - "
                            f"Tarea de vaciado ya existe"
                        )
                        continue
                    
                    # Crear tarea de vaciado
                    self.stdout.write(
                        f"  ✅ {servicio_nombre} - Reserva #{reserva.id}"
                    )
                    self.stdout.write(
                        f"     Fin servicio: {datetime_fin.strftime('%H:%M')}"
                    )
                    self.stdout.write(
                        f"     NO hay servicio siguiente → VACIAR"
                    )
                    
                    if not dry_run:
                        Task.objects.create(
                            title=f"Vaciar {servicio_nombre} – Reserva #{reserva.id}",
                            description=(
                                f"⏰ Servicio terminó a las {datetime_fin.strftime('%H:%M')}\n\n"
                                f"🔧 PROCEDIMIENTO DE VACIADO:\n"
                                f"• Verificar que cliente ya salió\n"
                                f"• Vaciar completamente la tina\n"
                                f"• Limpiar y sanitizar\n"
                                f"• Lavar filtros si es necesario\n"
                                f"• Apagar calefacción de esta tina\n"
                                f"• Dejar lista para próximo uso\n\n"
                                f"⚠️ IMPORTANTE: Solo vaciar si NO hay servicio inmediatamente después"
                            ),
                            swimlane=Swimlane.OPERACION,
                            owner=ops_user,
                            created_by=ops_user,
                            state=TaskState.BACKLOG,
                            queue_position=2,
                            reservation_id=str(reserva.id),
                            service_type='tina',
                            location_ref=tina_id,
                            source=TaskSource.SISTEMA,
                            promise_due_at=datetime_fin  # Vaciar cuando termine el servicio
                        )
                        tareas_creadas += 1
                        self.stdout.write(self.style.SUCCESS("       → Tarea de vaciado creada"))
                    else:
                        self.stdout.write("       [DRY-RUN]")
                
                except Exception as e:
                    errores += 1
                    logger.error(f"Error procesando servicio {rs.id}: {str(e)}")
        
        # Resumen
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(f"📊 Servicios de tinas revisados: {servicios_revisados}")
        self.stdout.write(f"⏭️  Con servicio siguiente (no vaciar): {servicios_con_siguiente}")
        self.stdout.write(f"✅ Tareas de vaciado creadas: {tareas_creadas}")
        if errores > 0:
            self.stdout.write(f"❌ Errores: {errores}")
        self.stdout.write("=" * 80 + "\n")
        
        if not dry_run and tareas_creadas > 0:
            self.stdout.write(self.style.SUCCESS(
                f"✅ {tareas_creadas} tarea(s) de vaciado generadas"
            ))
        elif servicios_revisados == 0:
            self.stdout.write(self.style.WARNING(
                "ℹ️  No hay servicios de tinas que hayan terminado recientemente"
            ))
        
        # Configuración cron
        self.stdout.write("\n" + self.style.WARNING("📌 CONFIGURACIÓN CRON:"))
        self.stdout.write("   Ejecutar cada 30 minutos:")
        self.stdout.write("   */30 * * * * python manage.py gen_vaciado_tinas\n")

