"""
Vistas para Control de Gestión

Incluye:
- Vistas web: mi_dia, equipo_snapshot, indicadores
- Webhooks: cliente_en_sitio, ai_ingest_message, ai_generate_checklist
- Acciones rápidas: cambiar estado de tareas (AJAX)
"""

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
import json
import logging
import os

from .models import (
    Task, TaskState, Priority, Swimlane, TaskSource, 
    ChecklistItem, LocationRef, TaskLog, DailyReport
)
from . import ai
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


@login_required
@require_http_methods(["POST"])
def cambiar_estado_tarea(request, task_id):
    """
    Vista AJAX para cambiar estado de tarea rápidamente
    
    POST /control_gestion/tarea/<id>/cambiar-estado/
    Body: {"nuevo_estado": "IN_PROGRESS" | "DONE" | "BLOCKED" | "BACKLOG"}
    
    Retorna JSON con resultado
    """
    task = get_object_or_404(Task, pk=task_id)
    
    # Verificar permisos: solo el owner o SUPERVISION/ADMIN pueden cambiar
    if not request.user.is_superuser:
        if not request.user.groups.filter(name='SUPERVISION').exists():
            if task.owner != request.user:
                return JsonResponse({
                    "ok": False,
                    "error": "No tienes permiso para modificar esta tarea"
                }, status=403)
    
    try:
        # Parsear nuevo estado
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        nuevo_estado = data.get('nuevo_estado', '').upper()
        
        # Validar estado
        estados_validos = [TaskState.BACKLOG, TaskState.IN_PROGRESS, TaskState.BLOCKED, TaskState.DONE]
        if nuevo_estado not in estados_validos:
            return JsonResponse({
                "ok": False,
                "error": f"Estado inválido. Debe ser uno de: {', '.join(estados_validos)}"
            }, status=400)
        
        # Cambiar estado
        estado_anterior = task.state
        task.state = nuevo_estado
        task.save()
        
        # Crear log
        TaskLog.objects.create(
            task=task,
            actor=request.user,
            action="STATE_CHANGED",
            note=f"Estado cambiado de {estado_anterior} a {nuevo_estado}"
        )
        
        logger.info(f"Tarea #{task.id} cambiada de {estado_anterior} a {nuevo_estado} por {request.user.username}")
        
        return JsonResponse({
            "ok": True,
            "task_id": task.id,
            "estado_anterior": estado_anterior,
            "nuevo_estado": nuevo_estado,
            "mensaje": f"Tarea cambiada a '{task.get_state_display()}'"
        })
        
    except ValidationError as e:
        return JsonResponse({
            "ok": False,
            "error": str(e)
        }, status=400)
    except Exception as e:
        logger.error(f"Error cambiando estado de tarea {task_id}: {str(e)}")
        return JsonResponse({
            "ok": False,
            "error": str(e)
        }, status=500)


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
    
    try:
        tasks = Task.objects.filter(
            updated_at__date=today
        ).select_related('owner').order_by('swimlane', 'queue_position')
        
        # Filtro por área si se especifica
        area_filter = request.GET.get('area', '')
        if area_filter:
            tasks = tasks.filter(swimlane=area_filter)
        
        # Estadísticas del día
        stats = {
            'total': tasks.count(),
            'done': tasks.filter(state=TaskState.DONE).count(),
            'in_progress': tasks.filter(state=TaskState.IN_PROGRESS).count(),
            'blocked': tasks.filter(state=TaskState.BLOCKED).count(),
            'backlog': tasks.filter(state=TaskState.BACKLOG).count(),
        }
        
        # Verificar si usuario está en grupo SUPERVISION de forma segura
        is_supervision = False
        if request.user.is_authenticated:
            try:
                is_supervision = request.user.groups.filter(name='SUPERVISION').exists()
            except Exception as e:
                logger.warning(f"Error verificando grupo SUPERVISION: {str(e)}")
                is_supervision = False
        
        context = {
            'tasks': tasks,
            'stats': stats,
            'today': today,
            'area_filter': area_filter,
            'user': request.user,
            'is_supervision': is_supervision
        }
        
        return render(request, "control_gestion/equipo.html", context)
    
    except Exception as e:
        logger.error(f"Error en equipo_snapshot: {str(e)}", exc_info=True)
        # Retornar página de error o página vacía
        context = {
            'tasks': Task.objects.none(),
            'stats': {'total': 0, 'done': 0, 'in_progress': 0, 'blocked': 0, 'backlog': 0},
            'today': today,
            'area_filter': '',
            'user': request.user,
            'is_supervision': False,
            'error': str(e)
        }
        return render(request, "control_gestion/equipo.html", context)


@login_required
def indicadores(request):
    """
    Vista de Indicadores/KPIs - Dashboard de métricas
    
    Muestra:
    - KPI por persona: tareas hechas/bloqueadas/promedio días
    - KPI por área: eficiencia, bloqueos >24h
    - Promesas cumplidas vs vencidas
    """
    from django.db.models import Count, Avg, Q
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.localdate()
    thirty_days_ago = today - timedelta(days=30)
    
    # ===== KPIs POR PERSONA =====
    kpis_persona = []
    
    # Obtener todos los usuarios que tienen tareas
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    usuarios_con_tareas = User.objects.filter(
        owned_tasks__isnull=False
    ).distinct()
    
    for usuario in usuarios_con_tareas:
        tareas_usuario = Task.objects.filter(owner=usuario)
        tareas_30d = tareas_usuario.filter(created_at__date__gte=thirty_days_ago)
        
        hechas = tareas_30d.filter(state=TaskState.DONE).count()
        bloqueadas = tareas_30d.filter(state=TaskState.BLOCKED).count()
        en_curso = tareas_30d.filter(state=TaskState.IN_PROGRESS).count()
        total = tareas_30d.count()
        
        # Calcular promedio de días para completar tareas
        tareas_completadas = tareas_30d.filter(
            state=TaskState.DONE,
            created_at__isnull=False,
            updated_at__isnull=False
        )
        
        promedio_dias = None
        if tareas_completadas.exists():
            tiempos = []
            for tarea in tareas_completadas:
                if tarea.created_at and tarea.updated_at:
                    delta = (tarea.updated_at.date() - tarea.created_at.date()).days
                    if delta >= 0:
                        tiempos.append(delta)
            
            if tiempos:
                promedio_dias = sum(tiempos) / len(tiempos)
        
        # Tareas bloqueadas >24h
        bloqueadas_24h = tareas_30d.filter(
            state=TaskState.BLOCKED,
            updated_at__lt=timezone.now() - timedelta(hours=24)
        ).count()
        
        kpis_persona.append({
            'usuario': usuario,
            'hechas': hechas,
            'bloqueadas': bloqueadas,
            'en_curso': en_curso,
            'total': total,
            'promedio_dias': round(promedio_dias, 1) if promedio_dias else None,
            'bloqueadas_24h': bloqueadas_24h,
            'eficiencia': round((hechas / total * 100), 1) if total > 0 else 0
        })
    
    # Ordenar por eficiencia descendente
    kpis_persona.sort(key=lambda x: x['eficiencia'], reverse=True)
    
    # ===== KPIs POR ÁREA (SWIMLANE) =====
    kpis_area = []
    
    for swimlane_code, swimlane_name in Swimlane.choices:
        tareas_area = Task.objects.filter(swimlane=swimlane_code)
        tareas_area_30d = tareas_area.filter(created_at__date__gte=thirty_days_ago)
        
        hechas = tareas_area_30d.filter(state=TaskState.DONE).count()
        bloqueadas = tareas_area_30d.filter(state=TaskState.BLOCKED).count()
        total = tareas_area_30d.count()
        
        # Bloqueos >24h
        bloqueadas_24h = tareas_area_30d.filter(
            state=TaskState.BLOCKED,
            updated_at__lt=timezone.now() - timedelta(hours=24)
        ).count()
        
        kpis_area.append({
            'area': swimlane_name,
            'codigo': swimlane_code,
            'hechas': hechas,
            'bloqueadas': bloqueadas,
            'total': total,
            'bloqueadas_24h': bloqueadas_24h,
            'eficiencia': round((hechas / total * 100), 1) if total > 0 else 0
        })
    
    # Ordenar por total descendente
    kpis_area.sort(key=lambda x: x['total'], reverse=True)
    
    # ===== PROMESAS CUMPLIDAS VS VENCIDAS =====
    from django.db.models import F
    
    promesas_cumplidas = Task.objects.filter(
        promise_due_at__isnull=False,
        state=TaskState.DONE
    ).filter(updated_at__lte=F('promise_due_at')).count()
    
    promesas_vencidas = Task.objects.filter(
        promise_due_at__isnull=False,
        promise_due_at__lt=timezone.now(),
        state__in=[TaskState.BACKLOG, TaskState.IN_PROGRESS, TaskState.BLOCKED]
    ).count()
    
    promesas_pendientes = Task.objects.filter(
        promise_due_at__isnull=False,
        promise_due_at__gte=timezone.now(),
        state__in=[TaskState.BACKLOG, TaskState.IN_PROGRESS]
    ).count()
    
    total_promesas = promesas_cumplidas + promesas_vencidas + promesas_pendientes
    tasa_cumplimiento = round((promesas_cumplidas / total_promesas * 100), 1) if total_promesas > 0 else 0
    
    # ===== ESTADÍSTICAS GENERALES =====
    stats_generales = {
        'total_tareas_30d': Task.objects.filter(created_at__date__gte=thirty_days_ago).count(),
        'tareas_hechas_30d': Task.objects.filter(
            created_at__date__gte=thirty_days_ago,
            state=TaskState.DONE
        ).count(),
        'tareas_bloqueadas_ahora': Task.objects.filter(state=TaskState.BLOCKED).count(),
        'tareas_en_curso': Task.objects.filter(state=TaskState.IN_PROGRESS).count(),
        'promesas_cumplidas': promesas_cumplidas,
        'promesas_vencidas': promesas_vencidas,
        'promesas_pendientes': promesas_pendientes,
        'tasa_cumplimiento': tasa_cumplimiento
    }
    
    context = {
        'kpis_persona': kpis_persona,
        'kpis_area': kpis_area,
        'stats_generales': stats_generales,
        'fecha_desde': thirty_days_ago,
        'fecha_hasta': today
    }
    
    return render(request, "control_gestion/indicadores.html", context)


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


@login_required
def reportes_diarios(request):
    """
    Vista de reportes diarios generados por IA
    
    Muestra los últimos reportes matutinos y vespertinos.
    """
    # Obtener últimos 7 días de reportes
    reportes = DailyReport.objects.all().order_by('-date')[:14]
    
    # Estadísticas
    stats = {
        'total': DailyReport.objects.count(),
        'ultima_semana': DailyReport.objects.filter(
            date__gte=timezone.now().date() - timedelta(days=7)
        ).count()
    }
    
    context = {
        'reportes': reportes,
        'stats': stats,
        'today': timezone.localdate()
    }
    
    return render(request, "control_gestion/reportes_diarios.html", context)

