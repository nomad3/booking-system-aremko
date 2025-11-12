"""
Vistas para endpoints de cron jobs de premios
Permiten ejecutar comandos Django via HTTP desde cron-job.org
"""
from django.http import JsonResponse
from django.core.management import call_command
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from io import StringIO
import os
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def cron_procesar_premios_bienvenida(request):
    """
    Endpoint para ejecutar procesar_premios_bienvenida desde cron externo

    GET o POST: /ventas/cron/procesar-premios-bienvenida/?token=xxx

    Qué hace:
    - Detecta clientes con check-in hace 3 días
    - Verifica si es cliente nuevo (servicios_historicos == 0)
    - Genera Premio de Bienvenida para clientes nuevos
    - Calcula tramo y genera Premio por Hito para clientes recurrentes

    Frecuencia recomendada: 1 vez al día - 8:00 AM
    """
    # Validar token de seguridad
    expected_token = os.getenv('CRON_TOKEN')
    if expected_token:
        request_token = request.GET.get('token') or request.POST.get('token')
        if request_token != expected_token:
            logger.warning("❌ Intento de acceso a cron con token inválido")
            return JsonResponse({"ok": False, "error": "Token inválido"}, status=403)

    try:
        # Capturar output del comando
        output = StringIO()
        call_command('procesar_premios_bienvenida', stdout=output)

        logger.info("✅ Cron procesar_premios_bienvenida ejecutado vía HTTP")

        return JsonResponse({
            "ok": True,
            "message": "Procesamiento de premios de bienvenida ejecutado",
            "command": "procesar_premios_bienvenida",
            "output": output.getvalue()
        })

    except Exception as e:
        logger.error(f"❌ Error en cron procesar_premios_bienvenida: {e}", exc_info=True)
        return JsonResponse({
            "ok": False,
            "error": str(e),
            "command": "procesar_premios_bienvenida"
        }, status=500)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def cron_enviar_premios_aprobados(request):
    """
    Endpoint para ejecutar enviar_premios_aprobados desde cron externo

    GET o POST: /ventas/cron/enviar-premios-aprobados/?token=xxx

    Qué hace:
    - Busca premios con estado='aprobado'
    - Envía emails a clientes con código de premio
    - Actualiza estado a 'enviado'
    - Respeta rate limiting (30 min entre envíos)
    - Envía 1 premio por ejecución (anti-spam)

    Frecuencia recomendada: Cada 30 minutos
    """
    # Validar token de seguridad
    expected_token = os.getenv('CRON_TOKEN')
    if expected_token:
        request_token = request.GET.get('token') or request.POST.get('token')
        if request_token != expected_token:
            logger.warning("❌ Intento de acceso a cron con token inválido")
            return JsonResponse({"ok": False, "error": "Token inválido"}, status=403)

    try:
        # Capturar output del comando
        output = StringIO()
        call_command('enviar_premios_aprobados', stdout=output)

        logger.info("✅ Cron enviar_premios_aprobados ejecutado vía HTTP")

        return JsonResponse({
            "ok": True,
            "message": "Envío de premios aprobados ejecutado",
            "command": "enviar_premios_aprobados",
            "output": output.getvalue()
        })

    except Exception as e:
        logger.error(f"❌ Error en cron enviar_premios_aprobados: {e}", exc_info=True)
        return JsonResponse({
            "ok": False,
            "error": str(e),
            "command": "enviar_premios_aprobados"
        }, status=500)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def cron_triggers_surveys(request):
    """
    Endpoint para ejecutar send_communication_triggers --type=surveys desde cron externo

    GET o POST: /ventas/cron/triggers-surveys/?token=xxx

    Qué hace:
    - Envía encuestas de satisfacción a clientes 24h después del servicio
    - Respeta límites anti-spam (1 email/semana, 4 emails/mes)
    - Horario: 9:00 AM - 8:00 PM
    - Usa plantillas personalizadas de encuesta

    Frecuencia recomendada: Diario 11:00 AM
    """
    # Validar token de seguridad
    expected_token = os.getenv('CRON_TOKEN')
    if expected_token:
        request_token = request.GET.get('token') or request.POST.get('token')
        if request_token != expected_token:
            logger.warning("❌ Intento de acceso a cron con token inválido")
            return JsonResponse({"ok": False, "error": "Token inválido"}, status=403)

    try:
        # Capturar output del comando
        output = StringIO()
        call_command('send_communication_triggers', type='surveys', stdout=output)

        logger.info("✅ Cron send_communication_triggers (surveys) ejecutado vía HTTP")

        return JsonResponse({
            "ok": True,
            "message": "Triggers de encuestas de satisfacción ejecutados",
            "command": "send_communication_triggers --type=surveys",
            "output": output.getvalue()
        })

    except Exception as e:
        logger.error(f"❌ Error en cron triggers surveys: {e}", exc_info=True)
        return JsonResponse({
            "ok": False,
            "error": str(e),
            "command": "send_communication_triggers --type=surveys"
        }, status=500)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def cron_triggers_reactivation(request):
    """
    Endpoint para ejecutar send_communication_triggers --type=reactivation desde cron externo

    GET o POST: /ventas/cron/triggers-reactivation/?token=xxx

    Qué hace:
    - Envía emails de reactivación a clientes inactivos 90+ días
    - Respeta límites anti-spam (1 email/trimestre por cliente)
    - Horario: 9:00 AM - 8:00 PM
    - Ofertas personalizadas para recuperar clientes

    Frecuencia recomendada: Lunes 9:00 AM (semanal)
    """
    # Validar token de seguridad
    expected_token = os.getenv('CRON_TOKEN')
    if expected_token:
        request_token = request.GET.get('token') or request.POST.get('token')
        if request_token != expected_token:
            logger.warning("❌ Intento de acceso a cron con token inválido")
            return JsonResponse({"ok": False, "error": "Token inválido"}, status=403)

    try:
        # Capturar output del comando
        output = StringIO()
        call_command('send_communication_triggers', type='reactivation', stdout=output)

        logger.info("✅ Cron send_communication_triggers (reactivation) ejecutado vía HTTP")

        return JsonResponse({
            "ok": True,
            "message": "Triggers de reactivación de clientes ejecutados",
            "command": "send_communication_triggers --type=reactivation",
            "output": output.getvalue()
        })

    except Exception as e:
        logger.error(f"❌ Error en cron triggers reactivation: {e}", exc_info=True)
        return JsonResponse({
            "ok": False,
            "error": str(e),
            "command": "send_communication_triggers --type=reactivation"
        }, status=500)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def cron_enviar_emails_programados(request):
    """
    Endpoint para ejecutar enviar_emails_programados desde cron externo

    GET o POST: /ventas/cron/enviar-emails-programados/?token=xxx

    Qué hace:
    - Procesa cola de emails del modelo MailParaEnviar
    - Envía batch de 2 emails por ejecución (configurable)
    - Respeta horario permitido: 8:00 AM - 6:00 PM (Chile)
    - Rate limiting anti-spam integrado
    - Estados: PENDIENTE → ENVIADO/ERROR

    Frecuencia recomendada: Cada 30 minutos (solo en horario laboral)
    """
    # Validar token de seguridad
    expected_token = os.getenv('CRON_TOKEN')
    if expected_token:
        request_token = request.GET.get('token') or request.POST.get('token')
        if request_token != expected_token:
            logger.warning("❌ Intento de acceso a cron con token inválido")
            return JsonResponse({"ok": False, "error": "Token inválido"}, status=403)

    try:
        # Capturar output del comando
        output = StringIO()
        call_command('enviar_emails_programados', stdout=output)

        logger.info("✅ Cron enviar_emails_programados ejecutado vía HTTP")

        return JsonResponse({
            "ok": True,
            "message": "Envío de emails programados ejecutado",
            "command": "enviar_emails_programados",
            "output": output.getvalue()
        })

    except Exception as e:
        logger.error(f"❌ Error en cron enviar_emails_programados: {e}", exc_info=True)
        return JsonResponse({
            "ok": False,
            "error": str(e),
            "command": "enviar_emails_programados"
        }, status=500)
