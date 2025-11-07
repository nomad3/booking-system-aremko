"""
Funciones IA de Negocio para Control de Gestión

Este módulo contiene las funciones de inteligencia artificial que automatizan
procesos del sistema de gestión:

1. message_to_task: Convertir mensaje de cliente → tarea estructurada
2. generate_checklist: Generar checklist contextual para SOPs
3. summarize_day: Resumen diario con IA para WhatsApp/Email
4. classify_priority: Clasificar prioridad de solicitudes
5. qa_task_completion: QA inteligente al cerrar tareas
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging

from .ai_client import LLMClient

logger = logging.getLogger(__name__)

# Cliente LLM global
_client = LLMClient()


def message_to_task(msg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convierte un mensaje de cliente en una tarea estructurada
    
    Args:
        msg: Dict con keys:
            - texto: Mensaje del cliente
            - canal: "whatsapp", "llamada", "presencial", etc.
            - contexto: Dict opcional con ubicacion, cliente, etc.
    
    Returns:
        Dict con estructura de tarea:
        {
            "title": str,
            "description": str,
            "checklist": List[str],
            "priority": "NORMAL" | "ALTA_CLIENTE_EN_SITIO",
            "suggested_owner_role": "RECEPCION" | "OPERACION" | etc,
            "promise_due_at": str (ISO datetime),
            "location_ref": str (opcional)
        }
    """
    system = (
        "Eres un asistente de gestión operativa para un spa en Chile. "
        "Convierte el siguiente mensaje del cliente en una Tarea concreta y accionable. "
        "Responde SOLO con JSON válido con las siguientes claves:\n"
        "- title: Título corto y claro (máx 100 caracteres)\n"
        "- description: Descripción detallada de qué hacer\n"
        "- checklist: Array de 3-7 pasos específicos\n"
        "- priority: 'NORMAL' o 'ALTA_CLIENTE_EN_SITIO' (si requiere atención inmediata)\n"
        "- suggested_owner_role: 'RECEPCION', 'OPERACION', 'ATENCION', 'COMERCIAL', 'SUPERVISION'\n"
        "- promise_due_at: Fecha/hora estimada de entrega (ISO format, zona America/Santiago)\n"
        "- location_ref: Ubicación si aplica (ej: 'TINA_4', 'CAB_2', 'RECEPCION')\n"
        "Usa español de Chile. Se específico y práctico."
    )
    
    user = json.dumps(msg, ensure_ascii=False, indent=2)
    
    try:
        raw = _client.complete(system, user)
        data = json.loads(raw)
        
        # Validar que tenga las keys requeridas
        required_keys = ['title', 'description', 'priority']
        for key in required_keys:
            if key not in data:
                raise ValueError(f"Respuesta IA sin key requerida: {key}")
        
        # Defaults para keys opcionales
        data.setdefault('checklist', [])
        data.setdefault('suggested_owner_role', 'RECEPCION')
        data.setdefault('location_ref', '')
        
        # Calcular promise_due_at si no viene
        if 'promise_due_at' not in data or not data['promise_due_at']:
            # Default: 2 horas si es ALTA, 24 horas si es NORMAL
            horas = 2 if data['priority'] == 'ALTA_CLIENTE_EN_SITIO' else 24
            data['promise_due_at'] = (
                datetime.now() + timedelta(hours=horas)
            ).isoformat()
        
        logger.info(f"message_to_task exitoso: {data['title']}")
        return data
    
    except json.JSONDecodeError as e:
        logger.error(f"Error parseando JSON de IA: {str(e)}")
        # Fallback manual
        texto = msg.get("texto", "")
        return {
            "title": f"Atender: {texto[:80]}",
            "description": texto[:500],
            "checklist": [
                "Recibir y confirmar solicitud",
                "Preparar recursos necesarios",
                "Ejecutar tarea",
                "Verificar y documentar resultado"
            ],
            "priority": "ALTA_CLIENTE_EN_SITIO" if any(
                palabra in texto.lower() 
                for palabra in ["urgente", "inmediato", "ahora", "tina", "cabaña"]
            ) else "NORMAL",
            "suggested_owner_role": "RECEPCION",
            "promise_due_at": (datetime.now() + timedelta(hours=2)).isoformat(),
            "location_ref": msg.get("contexto", {}).get("ubicacion", "")
        }
    
    except Exception as e:
        logger.error(f"Error en message_to_task: {str(e)}")
        raise


def generate_checklist(ctx: Dict[str, Any]) -> List[str]:
    """
    Genera checklist contextual para una tarea
    
    Args:
        ctx: Dict con contexto:
            - swimlane: Área responsable
            - servicio: Tipo de servicio (opcional)
            - ubicacion: Ubicación física (opcional)
            - titulo: Título de la tarea (opcional)
            - descripcion: Descripción de la tarea (opcional)
    
    Returns:
        Lista de 5-9 pasos para el checklist
    """
    system = (
        "Eres un experto en SOPs operativos para spas. "
        "Genera un checklist mínimo, claro y seguro para la tarea indicada. "
        "El checklist debe tener entre 5 y 9 pasos. "
        "Cada paso debe ser:\n"
        "- Una acción clara con verbo imperativo\n"
        "- Específico y verificable\n"
        "- En español de Chile\n"
        "- Máximo 1 línea (80 caracteres)\n"
        "Responde con un array JSON de strings."
    )
    
    user = json.dumps(ctx, ensure_ascii=False, indent=2)
    
    try:
        text = _client.complete(system, user)
        
        # Intentar parsear como JSON
        try:
            arr = json.loads(text)
            if isinstance(arr, list) and arr:
                checklist = [str(x).strip() for x in arr][:9]
                logger.info(f"Checklist generado: {len(checklist)} items")
                return checklist
        except json.JSONDecodeError:
            pass
        
        # Si no es JSON válido, parsear como texto
        lines = [
            ln.strip().lstrip("-•123456789. ")
            for ln in text.split("\n")
            if ln.strip() and not ln.strip().startswith("#")
        ]
        checklist = [ln for ln in lines if ln][:9]
        
        if not checklist:
            raise ValueError("Checklist vacío después de parsear")
        
        logger.info(f"Checklist generado (texto): {len(checklist)} items")
        return checklist
    
    except Exception as e:
        logger.error(f"Error generando checklist: {str(e)}")
        
        # Fallback: checklist genérico según swimlane
        swimlane = ctx.get("swimlane", "")
        
        if swimlane == "OPS":
            return [
                "Verificar limpieza del área",
                "Preparar insumos y materiales",
                "Verificar temperatura/condiciones",
                "Ejecutar tarea según SOP",
                "Inspección final de calidad",
                "Registrar en sistema"
            ]
        elif swimlane == "RX":
            return [
                "Recibir al cliente cordialmente",
                "Verificar reserva en sistema",
                "Confirmar pago/documento",
                "Explicar indicaciones",
                "Coordinar con área operativa"
            ]
        else:
            return [
                "Preparar área de trabajo",
                "Verificar insumos necesarios",
                "Ejecutar tarea",
                "Verificar calidad",
                "Registrar y documentar"
            ]


def summarize_day(stats: Dict[str, Any]) -> str:
    """
    Genera resumen diario motivante para el equipo
    
    Args:
        stats: Dict con estadísticas:
            - fecha: str
            - hechas: int
            - en_curso: int
            - bloqueadas: int
            - por_area: Dict[swimlane, Dict[hechas, pendientes]]
    
    Returns:
        Resumen en español, formato WhatsApp/Email
    """
    system = (
        "Eres el asistente de gestión de un spa en Chile. "
        "Redacta un resumen diario breve, claro y motivante para enviar al equipo "
        "por WhatsApp al final del día. "
        "El resumen debe:\n"
        "- Usar bullets (•) para listas\n"
        "- Mencionar tareas HECHAS, EN CURSO, BLOQUEADAS\n"
        "- Destacar logros del equipo\n"
        "- Indicar 3 prioridades para mañana\n"
        "- Ser conciso (máx 300 palabras)\n"
        "- Tono profesional pero amable\n"
        "- Español de Chile\n"
        "Formato para WhatsApp (sin markdown complex)."
    )
    
    user = json.dumps(stats, ensure_ascii=False, indent=2)
    
    try:
        resumen = _client.complete(system, user)
        logger.info("Resumen diario generado")
        return resumen
    
    except Exception as e:
        logger.error(f"Error generando resumen: {str(e)}")
        
        # Fallback manual
        fecha = stats.get('fecha', 'hoy')
        hechas = stats.get('hechas', 0)
        en_curso = stats.get('en_curso', 0)
        bloqueadas = stats.get('bloqueadas', 0)
        
        return (
            f"📊 *Resumen {fecha}*\n\n"
            f"✅ Completadas: {hechas}\n"
            f"⏳ En curso: {en_curso}\n"
            f"🚫 Bloqueadas: {bloqueadas}\n\n"
            f"🎯 *Prioridades para mañana:*\n"
            f"• Resolver tareas bloqueadas\n"
            f"• Completar tareas en curso\n"
            f"• Preparar servicios del día\n\n"
            f"¡Buen trabajo equipo! 💪"
        )


def classify_priority(txt: str) -> Dict[str, str]:
    """
    Clasifica la prioridad de un mensaje o solicitud
    
    Args:
        txt: Texto del mensaje/solicitud
    
    Returns:
        Dict con:
            - priority: "ALTA_CLIENTE_EN_SITIO" | "NORMAL"
            - reason: Explicación breve
    """
    system = (
        "Clasifica la prioridad de la siguiente solicitud para un spa. "
        "Responde SOLO con JSON:\n"
        "{\n"
        '  "priority": "ALTA_CLIENTE_EN_SITIO" | "NORMAL",\n'
        '  "reason": "Explicación breve"\n'
        "}\n\n"
        "Usa ALTA_CLIENTE_EN_SITIO si:\n"
        "- Cliente está en el sitio esperando atención\n"
        "- Urgencia operativa inmediata (ej: falta algo en tina/cabaña ocupada)\n"
        "- Problema que afecta experiencia del cliente NOW\n"
        "Usa NORMAL en otros casos."
    )
    
    user = txt[:4000]  # Limitar tamaño
    
    try:
        raw = _client.complete(system, user)
        result = json.loads(raw)
        
        # Validar estructura
        if 'priority' not in result:
            raise ValueError("Respuesta sin 'priority'")
        
        logger.info(f"Prioridad clasificada: {result['priority']}")
        return result
    
    except Exception as e:
        logger.error(f"Error clasificando prioridad: {str(e)}")
        
        # Fallback: análisis simple de palabras clave
        txt_lower = txt.lower()
        
        keywords_alta = [
            "urgente", "inmediato", "ahora", "ya", "rápido",
            "tina", "cabaña", "cliente", "sitio", "esperando",
            "falta", "problema", "no funciona"
        ]
        
        es_alta = any(keyword in txt_lower for keyword in keywords_alta)
        
        return {
            "priority": "ALTA_CLIENTE_EN_SITIO" if es_alta else "NORMAL",
            "reason": "Análisis de palabras clave (fallback)"
        }


def qa_task_completion(task: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, str]:
    """
    Evalúa si una tarea está bien completada
    
    Args:
        task: Dict con info de la tarea:
            - title: Título
            - description: Descripción
            - checklist: Lista de (text, done)
        evidence: Dict con evidencia:
            - notes: Notas del log
            - has_media: bool (si tiene foto/archivo)
            - logs_count: Número de logs
    
    Returns:
        Dict con:
            - status: "Completo" | "Incompleto" | "Dudoso"
            - motivo: Explicación
            - siguiente_accion: Qué hacer a continuación
    """
    system = (
        "Eres un supervisor de calidad para un spa. "
        "Evalúa si la tarea está bien completada según checklist y evidencias. "
        "Responde SOLO con JSON:\n"
        "{\n"
        '  "status": "Completo" | "Incompleto" | "Dudoso",\n'
        '  "motivo": "Explicación clara",\n'
        '  "siguiente_accion": "Qué hacer (si aplica)"\n'
        "}\n\n"
        "Criterios:\n"
        "- Completo: Checklist 100%, evidencia suficiente\n"
        "- Incompleto: Checklist < 100% o sin evidencia crítica\n"
        "- Dudoso: Ambiguo, requiere revisión manual"
    )
    
    user = json.dumps(
        {"task": task, "evidence": evidence},
        ensure_ascii=False,
        indent=2
    )
    
    try:
        raw = _client.complete(system, user)
        result = json.loads(raw)
        
        # Validar estructura
        required = ['status', 'motivo', 'siguiente_accion']
        for key in required:
            if key not in result:
                raise ValueError(f"Respuesta sin key: {key}")
        
        logger.info(f"QA completado: {result['status']}")
        return result
    
    except Exception as e:
        logger.error(f"Error en QA: {str(e)}")
        
        # Fallback: QA básico manual
        checklist = task.get('checklist', [])
        total_items = len(checklist)
        done_items = sum(1 for item in checklist if len(item) > 1 and item[1])
        
        has_evidence = evidence.get('has_media') or evidence.get('notes')
        
        if total_items == 0:
            return {
                "status": "Dudoso",
                "motivo": "Tarea sin checklist - difícil verificar completitud",
                "siguiente_accion": "Agregar checklist para próximas tareas similares"
            }
        elif done_items == total_items and has_evidence:
            return {
                "status": "Completo",
                "motivo": f"Checklist completo ({done_items}/{total_items}) y con evidencia",
                "siguiente_accion": "Archivar y continuar"
            }
        elif done_items == total_items:
            return {
                "status": "Dudoso",
                "motivo": f"Checklist completo pero sin evidencia documentada",
                "siguiente_accion": "Considerar agregar foto/nota en próximas tareas"
            }
        else:
            return {
                "status": "Incompleto",
                "motivo": f"Checklist incompleto ({done_items}/{total_items})",
                "siguiente_accion": "Completar items pendientes o justificar por qué no aplican"
            }


def get_client_info() -> Dict[str, Any]:
    """
    Retorna información del cliente LLM configurado
    
    Returns:
        Dict con info del cliente (provider, model, is_mock)
    """
    return _client.get_info()

