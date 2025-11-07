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
from .models import Task, TaskLog, TaskState, Priority


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


# ===== FASE 2: INTEGRACIÓN CON VENTAS (SE IMPLEMENTARÁ EN ETAPA 3) =====

# Caché para guardar estado anterior de VentaReserva
_old_estado_cache = {}


# Los siguientes signals se activarán en Etapa 3 cuando tengamos la integración completa

# @receiver(pre_save, sender='ventas.VentaReserva')
# def capture_old_estado(sender, instance, **kwargs):
#     """Captura el estado anterior de la reserva"""
#     # Se implementará en Etapa 3
#     pass


# @receiver(post_save, sender='ventas.VentaReserva')
# def react_to_reserva_change(sender, instance, created, **kwargs):
#     """Crea tareas automáticas al cambiar estado de reserva (checkin/checkout)"""
#     # Se implementará en Etapa 3
#     pass

