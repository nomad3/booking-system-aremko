"""
Vistas para Control de Gestión

Incluye:
- Vistas web: mi_dia, equipo_snapshot
- Webhooks: cliente_en_sitio, ai_ingest_message, ai_generate_checklist
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.auth import get_user_model
import json
import logging
import os

from .models import (
    Task, TaskState, Priority, Swimlane, TaskSource, 
    ChecklistItem, LocationRef
)
from . import ai

logger = logging.getLogger(__name__)
User = get_user_model()


@login_required
def mi_dia(request):
    """
    Vista "Mi Día" - Muestra las tareas top del usuario logueado
    
    Características:
    - Solo tareas del usuario actual
    - Excluye tareas DONE
    - Ordenadas por swimlane, cola, promesa
    - Límite de 3 tareas top (enfoque)
    """
    
    tasks = (
        Task.objects
        .filter(owner=request.user)
        .exclude(state=TaskState.DONE)
        .order_by("swimlane", "queue_position", "promise_due_at", "created_at")
    )[:3]
    
    context = {
        'tasks': tasks,
        'user': request.user,
        'total_pending': Task.objects.filter(
            owner=request.user
        ).exclude(state=TaskState.DONE).count()
    }
    
    return render(request, "control_gestion/mi_dia.html", context)


@login_required
def equipo_snapshot(request):
    """
    Vista "Equipo" - Snapshot de todas las tareas del día
    
    Muestra tareas de todo el equipo actualizadas hoy.
    """
    
    today = timezone.localdate()
    
    tasks = Task.objects.filter(
        updated_at__date=today
    ).select_related('owner').order_by('swimlane', 'queue_position')
    
    # Estadísticas del día
    stats = {
        'total': tasks.count(),
        'done': tasks.filter(state=TaskState.DONE).count(),
        'in_progress': tasks.filter(state=TaskState.IN_PROGRESS).count(),
        'blocked': tasks.filter(state=TaskState.BLOCKED).count(),
        'backlog': tasks.filter(state=TaskState.BACKLOG).count(),
    }
    
    context = {
        'tasks': tasks,
        'stats': stats,
        'today': today
    }
    
    return render(request, "control_gestion/equipo.html", context)


@csrf_exempt
def webhook_cliente_en_sitio(request):
    """
    Webhook para atender solicitudes de clientes en sitio (prioridad ALTA)
    
    POST payload JSON:
    {
        "pedido": "tabla de quesos y dos jugos",
        "ubicacion": "TINA_4",
        "responsable_username": "recepcion_user",
        "reserva_id": "3851"
    }
    
    Crea una tarea con prioridad ALTA automáticamente.
    """
    
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Solo POST"}, status=405)
    
    try:
        # Parsear payload
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except Exception:
            payload = request.POST.dict()
        
        # Extraer datos
        pedido = payload.get("pedido", "requerimiento")
        ubicacion = payload.get("ubicacion", "")
        responsable_username = payload.get("responsable_username")
        reserva_id = payload.get("reserva_id", "")
        
        # Buscar usuario responsable
        owner = None
        if responsable_username:
            owner = User.objects.filter(username=responsable_username).first()
        
        if not owner:
            # Fallback: primer usuario del grupo RECEPCION
            owner = User.objects.filter(groups__name="RECEPCION").first()
        
        if not owner:
            # Fallback final: primer usuario disponible
            owner = User.objects.first()
        
        # Clasificar prioridad con IA
        txt = f"{pedido} {ubicacion} {reserva_id}"
        try:
            pr = ai.classify_priority(txt)
            priority = pr.get("priority", Priority.ALTA_CLIENTE_EN_SITIO)
            if priority not in [Priority.NORMAL, Priority.ALTA_CLIENTE_EN_SITIO]:
                priority = Priority.ALTA_CLIENTE_EN_SITIO
        except Exception:
            priority = Priority.ALTA_CLIENTE_EN_SITIO
        
        # Crear tarea
        task = Task.objects.create(
            title=f"Cliente en sitio – {pedido} ({ubicacion})",
            description=f"Atender inmediatamente. Ubicación: {ubicacion}. Pedido: {pedido}",
            swimlane=Swimlane.RECEPCION,
            owner=owner,
            state=TaskState.BACKLOG,
            priority=priority,
            reservation_id=reserva_id,
            location_ref=ubicacion if ubicacion in dict(LocationRef.choices) else "",
            created_by=owner,
            queue_position=1,
            source=TaskSource.SISTEMA
        )
        
        logger.info(f"✅ Tarea ALTA creada vía webhook: {task.id}")
        
        return JsonResponse({
            "ok": True,
            "task_id": task.id,
            "priority": priority,
            "message": "Tarea creada exitosamente"
        })
    
    except Exception as e:
        logger.error(f"Error en webhook_cliente_en_sitio: {str(e)}")
        return JsonResponse({
            "ok": False,
            "error": str(e)
        }, status=500)


@csrf_exempt
def ai_ingest_message(request):
    """
    Webhook para convertir mensaje de cliente en tarea con IA
    
    POST payload JSON:
    {
        "canal": "whatsapp",
        "texto": "Hola, estamos en la tina 4, ¿pueden traer café?",
        "contexto": {
            "ubicacion": "TINA_4",
            "cliente": "+56912345678",
            "reserva_id": "3851"
        }
    }
    
    Retorna sugerencia de tarea estructurada por IA.
    """
    
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Solo POST"}, status=405)
    
    try:
        # Parsear payload
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except Exception:
            payload = request.POST.dict()
        
        # Procesar con IA
        suggestion = ai.message_to_task(payload)
        
        logger.info(f"✅ Mensaje procesado con IA: {suggestion.get('title', '')}")
        
        return JsonResponse({
            "ok": True,
            "suggestion": suggestion,
            "message": "Mensaje procesado exitosamente"
        })
    
    except Exception as e:
        logger.error(f"Error en ai_ingest_message: {str(e)}")
        return JsonResponse({
            "ok": False,
            "error": str(e)
        }, status=500)


@csrf_exempt
def ai_generate_checklist(request):
    """
    Webhook para generar checklist contextual con IA
    
    POST payload JSON:
    {
        "swimlane": "OPS",
        "servicio": "TINA_HIDRO",
        "ubicacion": "TINA_4",
        "titulo": "Preparar tina",
        "descripcion": "Preparar tina 4 para cliente VIP"
    }
    
    Retorna checklist de 5-9 pasos.
    """
    
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Solo POST"}, status=405)
    
    try:
        # Parsear payload
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except Exception:
            payload = request.POST.dict()
        
        # Generar checklist con IA
        checklist = ai.generate_checklist(payload)
        
        logger.info(f"✅ Checklist generado: {len(checklist)} items")
        
        return JsonResponse({
            "ok": True,
            "checklist": checklist,
            "count": len(checklist)
        })
    
    except Exception as e:
        logger.error(f"Error en ai_generate_checklist: {str(e)}")
        return JsonResponse({
            "ok": False,
            "error": str(e)
        }, status=500)


# ===== ENDPOINTS PARA CRON EXTERNO =====

@csrf_exempt
def cron_preparacion_servicios(request):
    """
    Endpoint para ejecutar gen_preparacion_servicios desde cron externo
    
    GET o POST: /control_gestion/cron/preparacion-servicios/
    
    Opcionalmente puede recibir un token de seguridad:
    ?token=tu_token_secreto
    """
    # Validar token si está configurado
    expected_token = os.getenv('CRON_TOKEN')
    if expected_token:
        request_token = request.GET.get('token') or request.POST.get('token')
        if request_token != expected_token:
            return JsonResponse({"ok": False, "error": "Token inválido"}, status=403)
    
    try:
        from django.core.management import call_command
        from io import StringIO
        
        # Capturar output del comando
        output = StringIO()
        call_command('gen_preparacion_servicios', stdout=output)
        
        result = output.getvalue()
        
        logger.info("✅ Cron preparacion_servicios ejecutado vía HTTP")
        
        return JsonResponse({
            "ok": True,
            "message": "Comando ejecutado exitosamente",
            "output": result[:1000]  # Limitar output
        })
    
    except Exception as e:
        logger.error(f"Error en cron_preparacion_servicios: {str(e)}")
        return JsonResponse({
            "ok": False,
            "error": str(e)
        }, status=500)


@csrf_exempt  
def cron_daily_opening(request):
    """
    Endpoint para ejecutar gen_daily_opening desde cron externo
    
    GET o POST: /control_gestion/cron/daily-opening/
    """
    # Validar token
    expected_token = os.getenv('CRON_TOKEN')
    if expected_token:
        request_token = request.GET.get('token') or request.POST.get('token')
        if request_token != expected_token:
            return JsonResponse({"ok": False, "error": "Token inválido"}, status=403)
    
    try:
        from django.core.management import call_command
        from io import StringIO
        
        output = StringIO()
        call_command('gen_daily_opening', stdout=output)
        
        result = output.getvalue()
        
        logger.info("✅ Cron daily_opening ejecutado vía HTTP")
        
        return JsonResponse({
            "ok": True,
            "message": "Comando ejecutado exitosamente",
            "output": result[:1000]
        })
    
    except Exception as e:
        logger.error(f"Error en cron_daily_opening: {str(e)}")
        return JsonResponse({
            "ok": False,
            "error": str(e)
        }, status=500)


@csrf_exempt
def cron_vaciado_tinas(request):
    """
    Endpoint para ejecutar gen_vaciado_tinas desde cron externo
    
    GET o POST: /control_gestion/cron/vaciado-tinas/
    """
    # Validar token
    expected_token = os.getenv('CRON_TOKEN')
    if expected_token:
        request_token = request.GET.get('token') or request.POST.get('token')
        if request_token != expected_token:
            return JsonResponse({"ok": False, "error": "Token inválido"}, status=403)
    
    try:
        from django.core.management import call_command
        from io import StringIO
        
        output = StringIO()
        call_command('gen_vaciado_tinas', stdout=output)
        
        result = output.getvalue()
        
        logger.info("✅ Cron vaciado_tinas ejecutado vía HTTP")
        
        return JsonResponse({
            "ok": True,
            "message": "Comando ejecutado exitosamente",
            "output": result[:1000]
        })
    
    except Exception as e:
        logger.error(f"Error en cron_vaciado_tinas: {str(e)}")
        return JsonResponse({
            "ok": False,
            "error": str(e)
        }, status=500)


@csrf_exempt
def cron_daily_reports(request):
    """
    Endpoint para ejecutar gen_daily_reports desde cron externo
    
    GET o POST: /control_gestion/cron/daily-reports/?momento=matutino
    """
    # Validar token
    expected_token = os.getenv('CRON_TOKEN')
    if expected_token:
        request_token = request.GET.get('token') or request.POST.get('token')
        if request_token != expected_token:
            return JsonResponse({"ok": False, "error": "Token inválido"}, status=403)
    
    try:
        from django.core.management import call_command
        from io import StringIO
        
        momento = request.GET.get('momento', 'vespertino')
        
        output = StringIO()
        call_command('gen_daily_reports', momento=momento, stdout=output)
        
        result = output.getvalue()
        
        logger.info(f"✅ Cron daily_reports ({momento}) ejecutado vía HTTP")
        
        return JsonResponse({
            "ok": True,
            "message": "Comando ejecutado exitosamente",
            "momento": momento,
            "output": result[:1000]
        })
    
    except Exception as e:
        logger.error(f"Error en cron_daily_reports: {str(e)}")
        return JsonResponse({
            "ok": False,
            "error": str(e)
        }, status=500)

