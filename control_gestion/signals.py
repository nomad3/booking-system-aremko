"""
Signals para Control de Gestión

Fase 1 (Etapa 1): Signals internos del módulo
- Validación WIP=1 (una tarea en curso por persona)
- Prioridad ALTA va a top de cola
- Creación automática de logs
- QA automático al cerrar tarea

Fase 2 (Etapa 3): Integración con ventas.VentaReserva (check-in/checkout)
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Task, TaskLog, TaskState, Priority, Swimlane, TaskSource
import logging

logger = logging.getLogger(__name__)


# ===== FASE 1: SIGNALS INTERNOS DEL MÓDULO =====

@receiver(pre_save, sender=Task)
def enforce_rules(sender, instance, **kwargs):
    """
    Validación de reglas de negocio antes de guardar una tarea:
    
    1. WIP=1: Solo una tarea en curso por persona
    2. Prioridad ALTA va a posición 1 de la cola
    """
    
    # Regla WIP=1: Solo una tarea IN_PROGRESS por owner
    if instance.state == TaskState.IN_PROGRESS:
        # Verificar si el owner ya tiene otra tarea en curso
        otras_en_curso = Task.objects.filter(
            owner=instance.owner,
            state=TaskState.IN_PROGRESS
        ).exclude(pk=instance.pk if instance.pk else None)
        
        if otras_en_curso.exists():
            tarea_actual = otras_en_curso.first()
            raise ValidationError(
                f"WIP=1: Ya tienes una tarea 'En curso' ('{tarea_actual.title}'). "
                f"Debes completarla o bloquearla antes de iniciar otra."
            )
    
    # Prioridad ALTA va a top de cola
    if instance.priority == Priority.ALTA_CLIENTE_EN_SITIO:
        instance.queue_position = 1


@receiver(post_save, sender=Task)
def create_log_on_save(sender, instance, created, **kwargs):
    """
    Crea log automático al crear o actualizar una tarea
    """
    action = "CREATED" if created else "UPDATED"
    actor = instance.owner
    
    # Verificar que no se cree log duplicado (evitar recursión)
    ultimo_log = TaskLog.objects.filter(task=instance).order_by('-when').first()
    
    # Si ya existe un log muy reciente (< 1 segundo), no duplicar
    if ultimo_log:
        tiempo_desde_ultimo = (timezone.now() - ultimo_log.when).total_seconds()
        if tiempo_desde_ultimo < 1:
            return
    
    TaskLog.objects.create(
        task=instance,
        actor=actor,
        action=action,
        note=""
    )


@receiver(post_save, sender=Task)
def qa_on_done(sender, instance, created, **kwargs):
    """
    QA automático con IA cuando se marca una tarea como HECHA
    
    Se ejecutará en Etapa 2 cuando se implemente la capa de IA.
    Por ahora solo registra que la tarea fue completada.
    """
    
    # Solo ejecutar si la tarea acaba de marcarse como DONE (no en creación)
    if created or instance.state != TaskState.DONE:
        return
    
    # Verificar si ya se hizo QA recientemente
    qa_previo = TaskLog.objects.filter(
        task=instance,
        action="QA_RESULT"
    ).exists()
    
    if qa_previo:
        return
    
    # Preparar contexto de la tarea para QA
    task_ctx = {
        "title": instance.title,
        "description": instance.description,
        "checklist": list(instance.checklist.values_list("text", "done")),
        "checklist_count": instance.checklist.count(),
        "checklist_done": instance.checklist.filter(done=True).count()
    }
    
    evidence = {
        "notes": "; ".join([l.note for l in instance.logs.all() if l.note])[:1000],
        "has_media": bool(instance.media),
        "logs_count": instance.logs.count()
    }
    
    try:
        # Intentar usar IA (se implementará en Etapa 2)
        from . import ai
        result = ai.qa_task_completion(task_ctx, evidence)
        
        TaskLog.objects.create(
            task=instance,
            actor=instance.owner,
            action="QA_RESULT",
            note=f"{result.get('status')}: {result.get('motivo')} | Siguiente: {result.get('siguiente_accion')}"
        )
    except ImportError:
        # IA no disponible aún - QA manual básico
        checklist_completo = (
            task_ctx['checklist_count'] > 0 and 
            task_ctx['checklist_done'] == task_ctx['checklist_count']
        )
        
        if checklist_completo:
            status = "✅ Completo (checklist verificado)"
        elif task_ctx['checklist_count'] == 0:
            status = "⚠️ Sin checklist - verificar manualmente"
        else:
            status = f"⚠️ Checklist incompleto ({task_ctx['checklist_done']}/{task_ctx['checklist_count']})"
        
        TaskLog.objects.create(
            task=instance,
            actor=instance.owner,
            action="QA_RESULT",
            note=status
        )
    except Exception as e:
        # Error en QA - registrar pero no bloquear
        TaskLog.objects.create(
            task=instance,
            actor=instance.owner,
            action="QA_RESULT",
            note=f"⚠️ Error en QA automático: {str(e)}"
        )


# ===== FASE 2: INTEGRACIÓN CON VENTAS =====

# Caché para guardar estado anterior de VentaReserva
_old_estado_cache = {}


def _get_last9_digits(phone: str) -> str:
    """
    Extrae los últimos 9 dígitos de un teléfono
    
    Args:
        phone: Teléfono en cualquier formato (ej: +56912345678)
    
    Returns:
        Últimos 9 dígitos o string vacío
    """
    if not phone:
        return ""
    
    # Extraer solo dígitos
    digits = "".join([c for c in str(phone) if c.isdigit()])
    
    # Retornar últimos 9
    return digits[-9:] if len(digits) >= 9 else digits


def _get_user_by_group(group_name: str):
    """
    Obtiene el primer usuario de un grupo
    
    Args:
        group_name: Nombre del grupo
    
    Returns:
        User o None
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    return User.objects.filter(groups__name=group_name).first() or User.objects.first()


@receiver(pre_save, sender='ventas.VentaReserva')
def capture_old_estado(sender, instance, **kwargs):
    """
    Captura el estado_reserva anterior antes de guardar
    
    Esto permite detectar transiciones de estado (pendiente → checkin → checkout)
    """
    if instance.pk:
        try:
            # Importar dinámicamente para evitar circular imports
            from ventas.models import VentaReserva
            
            old = VentaReserva.objects.get(pk=instance.pk)
            _old_estado_cache[instance.pk] = old.estado_reserva
        except Exception:
            _old_estado_cache[instance.pk] = None
    else:
        _old_estado_cache[instance.pk] = None


@receiver(post_save, sender='ventas.VentaReserva')
def react_to_reserva_change(sender, instance, created, **kwargs):
    """
    Crea tareas automáticas cuando el recepcionista cambia estado_reserva
    
    Transiciones detectadas:
    - pendiente → checkin: Crear tareas de preparación (RECEPCION + OPERACION)
    - checkin → checkout: Crear tareas post-visita (NPS + premio D+3)
    
    Las tareas se crean automáticamente y se asignan a los usuarios
    correspondientes de cada grupo.
    """
    from datetime import datetime, timedelta
    from ventas.models import ReservaServicio
    
    # Obtener estado anterior
    old_estado = _old_estado_cache.pop(instance.pk, None)
    new_estado = instance.estado_reserva
    
    # Si no hay cambio de estado, no hacer nada
    if old_estado == new_estado:
        return
    
    # Obtener usuarios por grupo
    ops = _get_user_by_group("OPERACIONES")
    rx = _get_user_by_group("RECEPCION")
    com = _get_user_by_group("VENTAS")
    cs = _get_user_by_group("ATENCION") or com
    
    # Obtener teléfono del cliente (últimos 9 dígitos)
    customer_phone = _get_last9_digits(
        getattr(instance.cliente, "telefono", "") if instance.cliente else ""
    )
    
    # Obtener tramo del cliente (opcional, puede fallar si TramoService no disponible)
    segment_tag = ""
    try:
        from ventas.services.tramo_service import TramoService
        gasto_total = TramoService.calcular_gasto_cliente(instance.cliente)
        tramo_actual = TramoService.calcular_tramo(float(gasto_total))
        segment_tag = f"Tramo {tramo_actual}"
    except Exception as e:
        logger.warning(f"No se pudo calcular tramo del cliente: {str(e)}")
    
    # Obtener servicios asociados a esta reserva
    servicios = instance.reservaservicios.all()
    
    # ===== TRANSICIÓN A CHECKIN =====
    if old_estado != "checkin" and new_estado == "checkin":
        logger.info(f"Reserva #{instance.id} → CHECKIN. Creando tareas automáticas...")
        
        # Obtener hora del primer servicio para mostrar en título
        primer_servicio = servicios.first()
        hora_servicio = ""
        if primer_servicio:
            hora_servicio = f" ({primer_servicio.hora_inicio})"
        
        # Tarea para RECEPCIÓN (inmediata)
        Task.objects.create(
            title=f"Check-in confirmado – Reserva #{instance.id}{hora_servicio}",
            description=(
                "Dar la bienvenida al cliente, entregar indicaciones del spa, "
                "validar pago y documento si aplica, coordinar con Operaciones."
            ),
            swimlane=Swimlane.RECEPCION,
            owner=rx,
            created_by=rx,
            state=TaskState.BACKLOG,
            queue_position=1,
            reservation_id=str(instance.id),
            customer_phone_last9=customer_phone,
            segment_tag=segment_tag,
            priority=Priority.NORMAL,
            source=TaskSource.SISTEMA
        )
        logger.info(f"✅ Tarea RECEPCION creada para reserva #{instance.id}")
        
        # NOTA: Las tareas de preparación de servicios (OPERACION) 
        # NO se crean aquí en el check-in administrativo.
        # Se crean automáticamente 1 hora antes del servicio mediante el comando:
        # python manage.py gen_preparacion_servicios
        # 
        # Este comando debe ejecutarse cada hora vía cron:
        # 0 * * * * python manage.py gen_preparacion_servicios
        
        logger.info(
            f"ℹ️  Tareas de preparación de servicios se crearán automáticamente "
            f"1 hora antes vía comando gen_preparacion_servicios"
        )
    
    # ===== TRANSICIÓN A CHECKOUT =====
    elif old_estado != "checkout" and new_estado == "checkout":
        logger.info(f"Reserva #{instance.id} → CHECKOUT. Creando tareas post-visita...")
        
        # Usar hora REAL del checkout (cuando el recepcionista lo marca)
        hora_checkout_real = timezone.now().strftime('%H:%M')
        
        # Tarea para RECEPCIÓN (checkout/despedida)
        Task.objects.create(
            title=f"Checkout completado – Reserva #{instance.id} ({hora_checkout_real})",
            description=(
                "Procedimiento de checkout:\n"
                "- Despedir al cliente cordialmente\n"
                "- Verificar cobro final (si hay pendiente)\n"
                "- Preguntar: ¿Todo estuvo bien? (feedback rápido)\n"
                "- Agradecer la visita\n"
                "- Invitar a volver y recordar beneficios de fidelidad\n"
                "- Verificar que el área quede en orden"
            ),
            swimlane=Swimlane.RECEPCION,
            owner=rx,
            created_by=rx,
            state=TaskState.BACKLOG,
            queue_position=1,
            reservation_id=str(instance.id),
            customer_phone_last9=customer_phone,
            segment_tag=segment_tag,
            priority=Priority.NORMAL,
            source=TaskSource.SISTEMA
        )
        logger.info(f"✅ Tarea RECEPCION (checkout) creada para reserva #{instance.id}")
        
        # Tarea para ATENCIÓN AL CLIENTE (NPS) - también con hora real de checkout
        Task.objects.create(
            title=f"NPS post-visita – Reserva #{instance.id} ({hora_checkout_real})",
            description=(
                "Contactar al cliente por WhatsApp o llamada para:\n"
                "- Pedir calificación NPS (0-10)\n"
                "- Solicitar comentarios de la experiencia\n"
                "- Registrar feedback en CRM\n"
                "- Agradecer la visita"
            ),
            swimlane=Swimlane.ATENCION,
            owner=cs,
            created_by=cs,
            state=TaskState.BACKLOG,
            queue_position=1,
            reservation_id=str(instance.id),
            customer_phone_last9=customer_phone,
            segment_tag=segment_tag,
            priority=Priority.NORMAL,
            source=TaskSource.SISTEMA
        )
        logger.info(f"✅ Tarea NPS creada para reserva #{instance.id}")
        
        # Tareas para COMERCIAL (Premio D+3)
        # Crear una tarea por cada servicio, programada para D+3 después del check-in
        for rs in servicios:
            # Calcular fecha D+3 después del check-in
            try:
                due_at = datetime.combine(
                    rs.fecha_agendamiento,
                    datetime.min.time()
                ) + timedelta(days=3)
                
                # Convertir a aware datetime
                due_at = timezone.make_aware(due_at)
            except Exception:
                # Si falla, usar 3 días desde ahora
                due_at = timezone.now() + timedelta(days=3)
            
            servicio_nombre = getattr(rs.servicio, 'nombre', 'Servicio') if rs.servicio else 'Servicio'
            # Para premio, mostrar hora de inicio del servicio (referencia)
            hora_display = f" (Servicio {rs.hora_inicio})" if rs.hora_inicio else ""
            
            Task.objects.create(
                title=f"Verificar premio D+3 – Reserva #{instance.id}{hora_display}",
                description=(
                    f"Enviar premio según tramo del cliente ({segment_tag}):\n"
                    f"- Enviar por WhatsApp con mensaje personalizado\n"
                    f"- Enviar por Email con vale digital\n"
                    f"- (Opcional) SMS de respaldo\n"
                    f"- Registrar envío en sistema de premios\n"
                    f"- Validar que cliente recibió correctamente\n\n"
                    f"Servicio: {servicio_nombre}\n"
                    f"Check-in fue: {rs.fecha_agendamiento}"
                ),
                swimlane=Swimlane.COMERCIAL,
                owner=com,
                created_by=com,
                state=TaskState.BACKLOG,
                queue_position=1,
                reservation_id=str(instance.id),
                customer_phone_last9=customer_phone,
                segment_tag=segment_tag,
                service_type=getattr(rs.servicio, 'tipo_servicio', '') if rs.servicio else '',
                priority=Priority.NORMAL,
                source=TaskSource.SISTEMA,
                promise_due_at=due_at  # ⭐ Programada para D+3
            )
        
        logger.info(f"✅ {servicios.count()} tarea(s) PREMIO D+3 creadas para reserva #{instance.id}")
    
    else:
        # Otras transiciones no gatillan tareas automáticas por ahora
        logger.debug(f"Reserva #{instance.id}: {old_estado} → {new_estado} (sin tareas automáticas)")


