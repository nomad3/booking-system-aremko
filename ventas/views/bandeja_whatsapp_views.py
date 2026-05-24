"""
Endpoints REST para Operación Vuelta a Casa — Etapa 4.

Consumidos por el dashboard "Asistente Deborah" del frontend aremko-cli.

Prefijo de rutas: /ventas/api/aremko-cli/operacion-vuelta-a-casa/

Auth: header X-API-KEY contra settings.AUTOMATION_API_KEY (mismo patrón que
los endpoints write existentes: get_campaign_targets, etc.). Los endpoints
read-only de aremko-cli (bookings_stats, etc.) son públicos, pero estos
modifican BD (opt_out, ultimo_contacto_outbound, estado de contacto) →
requieren auth.

Endpoints:

    GET  bandeja-whatsapp/siguiente/                     → next item para procesar
    POST bandeja-whatsapp/<id>/marcar-enviado/           → operador envió manual
    POST bandeja-whatsapp/<id>/marcar-omitido/           → operador saltó hoy
    POST bandeja-whatsapp/<id>/marcar-no-aplica/         → tel inválido, etc.
    POST bandeja-whatsapp/<id>/registrar-respuesta/      → cliente respondió
    GET  bandeja-whatsapp/explicacion/<id>/              → stub (Etapa LLM futura)
    GET  bandeja-whatsapp/resumen-dia/?fecha=...         → stats del día
    GET  movimientos/?desde=...&hasta=...                → bitácora viva
    GET  scripts-estadisticas/?desde=...&hasta=...       → performance de plantillas
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from django.conf import settings
from django.db.models import Count, Sum, Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ventas.models import (
    Cliente,
    ContactoWhatsApp,
    EventoCelebracion,
    ScriptWhatsApp,
    TaxonomiaMovimiento,
    VentaReserva,
)


logger = logging.getLogger(__name__)


# Días tras enviar antes de considerar "respuesta pendiente de registrar"
VENTANA_RESPUESTA_PENDIENTE_MIN = 3
VENTANA_RESPUESTA_PENDIENTE_MAX = 7

# Período de gracia tras 'mas_adelante' (días)
GRACIA_MAS_ADELANTE = 60
# Período de gracia tras 'no_aplica' (días)
GRACIA_NO_APLICA = 90

# Orden canónico de eje_valor (mejor → peor). Usado para clasificar movimientos
# como positivos (mejora) o negativos (regresión).
ORDEN_VALOR = {
    'Campeón': 0,
    'Leal': 1,
    'Gran Gastador Ocasional': 2,
    'Regular': 3,
    'En Prueba': 4,
    'En Riesgo': 5,
    'Dormido': 6,
    'Pre-sistema': 7,
}


# ============================================================================
# Auth helper (mismo patrón que ventas.views.api_views.is_valid_api_key)
# ============================================================================

def _require_api_key(request) -> Optional[JsonResponse]:
    """Devuelve None si está autenticado, o JsonResponse 401 si no.

    Uso:
        err = _require_api_key(request)
        if err: return err
    """
    provided = request.headers.get('X-API-KEY')
    expected = getattr(settings, 'AUTOMATION_API_KEY', None) or None
    if not expected:
        # En entornos sin la env var, mejor cerrar el endpoint (no permitir
        # bypass por error de configuración).
        logger.warning("AUTOMATION_API_KEY no está configurada — endpoint cerrado")
        return JsonResponse(
            {'error': 'Server misconfigured: AUTOMATION_API_KEY missing'},
            status=503,
        )
    if not provided or provided != expected:
        return JsonResponse(
            {'error': 'Authentication required: send X-API-KEY header'},
            status=401,
        )
    return None


# ============================================================================
# Helpers internos compartidos
# ============================================================================

def _parse_fecha(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return None


def _serializar_perfil(cliente: Cliente, tax) -> dict:
    """Resumen del cliente para mostrar al operador en la bandeja."""
    ultima = tax.ultima_visita if tax else None
    return {
        'estado_valor': tax.eje_valor if tax else '',
        'dias_sin_venir': tax.dias_desde_ultima_visita if tax else None,
        'cohorte': (
            f"{tax.eje_estilo} × {tax.eje_contexto}" if tax else ''
        ),
        'visitas_totales': tax.total_visitas if tax else None,
        'gasto_historico': tax.gasto_total if tax else None,
        'ultima_visita': ultima.isoformat() if ultima else None,
    }


def _serializar_contacto(c: ContactoWhatsApp) -> dict:
    """Estructura del contacto para el frontend."""
    tax = getattr(c.cliente, 'taxonomia', None) if c.cliente else None
    telefono = c.cliente.telefono if c.cliente else ''
    return {
        'id': c.id,
        'cliente': {
            'id': c.cliente_id,
            'nombre': c.cliente.nombre if c.cliente else '',
            'telefono': telefono,
            'telefono_limpio': telefono.replace('+', '').replace(' ', '') if telefono else '',
        },
        'perfil_resumen': _serializar_perfil(c.cliente, tax),
        'script_id': c.script.script_id if c.script else '',
        'salva': c.salva,
        'mensaje_renderizado': c.mensaje_renderizado,
        'prioridad': c.prioridad,
        'fecha_sugerido': c.fecha_sugerido.isoformat() if c.fecha_sugerido else None,
        'estado': c.estado,
    }


def _progreso_dia(fecha_obj: date) -> dict:
    """Conteos rápidos del día para mostrar en la UI."""
    qs = ContactoWhatsApp.objects.filter(fecha_sugerido=fecha_obj)
    completados = qs.filter(estado__in=['enviado', 'omitido', 'no_aplica', 'descartado']).count()
    pendientes = qs.filter(estado='pendiente').count()

    # Respuestas pendientes: enviados hace 3-7 días sin tipo_respuesta marcado
    hoy = timezone.now().date()
    desde = hoy - timedelta(days=VENTANA_RESPUESTA_PENDIENTE_MAX)
    hasta = hoy - timedelta(days=VENTANA_RESPUESTA_PENDIENTE_MIN)
    respuestas_pendientes = ContactoWhatsApp.objects.filter(
        estado='enviado',
        fecha_envio__date__gte=desde,
        fecha_envio__date__lte=hasta,
        tipo_respuesta='',
    ).count()

    celebraciones_pendientes = EventoCelebracion.objects.filter(
        fecha=fecha_obj, mostrado_en_bandeja=False
    ).count()

    return {
        'completados_hoy': completados,
        'pendientes_hoy': pendientes,
        'respuestas_pendientes': respuestas_pendientes,
        'celebraciones_pendientes': celebraciones_pendientes,
    }


# ============================================================================
# 1. GET bandeja-whatsapp/siguiente/
# ============================================================================

@csrf_exempt
@require_http_methods(['GET'])
def siguiente(request):
    """Devuelve el próximo cliente a procesar para el operador.

    Orden:
      1. ContactoWhatsApp 'enviado' hace 3-7 días sin tipo_respuesta marcado
         → 'respuesta_pendiente' (operador debe registrar lo que pasó)
      2. EventoCelebracion no mostrado del día → 'celebracion'
      3. ContactoWhatsApp pendiente ordenado por (prioridad ASC, gasto DESC)
         → 'nuevo_contacto'
      4. Sin más nada → 'fin_del_dia' con resumen
    """
    err = _require_api_key(request)
    if err:
        return err

    hoy = timezone.now().date()

    # ---- 1. Respuestas pendientes (más antiguas primero) ----
    desde = hoy - timedelta(days=VENTANA_RESPUESTA_PENDIENTE_MAX)
    hasta = hoy - timedelta(days=VENTANA_RESPUESTA_PENDIENTE_MIN)
    resp_pend = (
        ContactoWhatsApp.objects
        .select_related('cliente', 'script')
        .filter(
            estado='enviado',
            fecha_envio__date__gte=desde,
            fecha_envio__date__lte=hasta,
            tipo_respuesta='',
        )
        .order_by('fecha_envio')
        .first()
    )
    if resp_pend:
        return JsonResponse({
            'tipo': 'respuesta_pendiente',
            'contacto': _serializar_contacto(resp_pend),
            'progreso': _progreso_dia(hoy),
        })

    # ---- 2. Celebraciones pendientes del día ----
    celeb = (
        EventoCelebracion.objects
        .select_related('cliente')
        .filter(fecha=hoy, mostrado_en_bandeja=False)
        .order_by('creado')
        .first()
    )
    if celeb:
        return JsonResponse({
            'tipo': 'celebracion',
            'celebracion': {
                'id': celeb.id,
                'tipo': celeb.tipo,
                'tipo_display': celeb.get_tipo_display(),
                'fecha': celeb.fecha.isoformat(),
                'mensaje_sugerido': celeb.mensaje_sugerido,
                'cliente': {
                    'id': celeb.cliente_id,
                    'nombre': celeb.cliente.nombre,
                    'telefono': celeb.cliente.telefono,
                },
            },
            'progreso': _progreso_dia(hoy),
        })

    # ---- 3. Próximo contacto pendiente del día ----
    nuevo = (
        ContactoWhatsApp.objects
        .select_related('cliente', 'script')
        .filter(fecha_sugerido=hoy, estado='pendiente')
        .order_by('prioridad', '-gasto_historico_snapshot', 'id')
        .first()
    )
    if nuevo:
        return JsonResponse({
            'tipo': 'nuevo_contacto',
            'contacto': _serializar_contacto(nuevo),
            'progreso': _progreso_dia(hoy),
        })

    # ---- 4. Fin del día ----
    return JsonResponse({
        'tipo': 'fin_del_dia',
        'resumen_dia': _build_resumen_dia(hoy),
        'progreso': _progreso_dia(hoy),
    })


# ============================================================================
# 2. POST bandeja-whatsapp/<id>/marcar-enviado/
# ============================================================================

@csrf_exempt
@require_http_methods(['POST'])
def marcar_enviado(request, contacto_id: int):
    """Operador marca un contacto como enviado tras hacer el WhatsApp manual.

    Body JSON:
        {
            "operador": "deborah",
            "mensaje_enviado_editado": "..."  // opcional
        }

    Revalidación en tiempo real:
        Si el eje_valor del cliente cambió desde fecha_sugerido (la madrugada
        cuando el cron generó la bandeja), marca el contacto como 'descartado'
        y devuelve 409 Conflict. El frontend muestra warning al operador.

    Side effects:
        - estado='enviado', fecha_envio=now(), operador, mensaje_enviado_editado
        - Cliente.ultimo_contacto_outbound = today  (clave para anti-saturación)

    Devuelve 200 con el siguiente_contacto pre-resuelto (ahorra round-trip).
    """
    import json

    err = _require_api_key(request)
    if err:
        return err

    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Body must be JSON'}, status=400)

    operador = (body.get('operador') or '').strip()
    mensaje_editado = body.get('mensaje_enviado_editado', '') or ''

    try:
        contacto = ContactoWhatsApp.objects.select_related('cliente').get(id=contacto_id)
    except ContactoWhatsApp.DoesNotExist:
        return JsonResponse({'error': f'ContactoWhatsApp {contacto_id} no existe'}, status=404)

    if contacto.estado != 'pendiente':
        return JsonResponse(
            {'error': f'Contacto en estado {contacto.estado!r}, no se puede marcar enviado'},
            status=400,
        )

    # ---- Revalidación: ¿el cliente cambió de estado desde la madrugada? ----
    tax = getattr(contacto.cliente, 'taxonomia', None)
    if tax and tax.eje_valor != contacto.eje_valor_snapshot:
        contacto.estado = 'descartado'
        contacto.save(update_fields=['estado'])
        return JsonResponse({
            'error': 'conflict',
            'mensaje': (
                f"El cliente cambió de '{contacto.eje_valor_snapshot}' a '{tax.eje_valor}' "
                f"desde que se generó la bandeja. Marcamos descartado."
            ),
            'eje_valor_anterior': contacto.eje_valor_snapshot,
            'eje_valor_actual': tax.eje_valor,
        }, status=409)

    now = timezone.now()
    contacto.estado = 'enviado'
    contacto.fecha_envio = now
    contacto.operador = operador
    if mensaje_editado:
        contacto.mensaje_enviado_editado = mensaje_editado
    contacto.save(update_fields=[
        'estado', 'fecha_envio', 'operador', 'mensaje_enviado_editado',
    ])

    # Actualizar anti-saturación en Cliente
    contacto.cliente.ultimo_contacto_outbound = now.date()
    contacto.cliente.save(update_fields=['ultimo_contacto_outbound'])

    # Pre-resolver siguiente_contacto para ahorrar round-trip
    siguiente_data = _resolver_siguiente_payload(now.date())

    return JsonResponse({
        'success': True,
        'contacto_id': contacto.id,
        'siguiente': siguiente_data,
    })


def _resolver_siguiente_payload(hoy: date) -> dict:
    """Versión inline de siguiente() que no requiere request (reuso interno)."""
    nuevo = (
        ContactoWhatsApp.objects
        .select_related('cliente', 'script')
        .filter(fecha_sugerido=hoy, estado='pendiente')
        .order_by('prioridad', '-gasto_historico_snapshot', 'id')
        .first()
    )
    if nuevo:
        return {
            'tipo': 'nuevo_contacto',
            'contacto': _serializar_contacto(nuevo),
            'progreso': _progreso_dia(hoy),
        }
    return {'tipo': 'fin_del_dia', 'progreso': _progreso_dia(hoy)}


# ============================================================================
# 3. POST bandeja-whatsapp/<id>/marcar-omitido/
# ============================================================================

@csrf_exempt
@require_http_methods(['POST'])
def marcar_omitido(request, contacto_id: int):
    """Operador decide no enviar a este cliente hoy. Queda elegible mañana."""
    err = _require_api_key(request)
    if err:
        return err

    try:
        contacto = ContactoWhatsApp.objects.get(id=contacto_id)
    except ContactoWhatsApp.DoesNotExist:
        return JsonResponse({'error': 'ContactoWhatsApp no existe'}, status=404)

    if contacto.estado != 'pendiente':
        return JsonResponse(
            {'error': f'Contacto en estado {contacto.estado!r}'},
            status=400,
        )

    import json
    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        body = {}

    contacto.estado = 'omitido'
    contacto.operador = (body.get('operador') or '').strip()
    contacto.save(update_fields=['estado', 'operador'])

    return JsonResponse({'success': True, 'contacto_id': contacto.id})


# ============================================================================
# 4. POST bandeja-whatsapp/<id>/marcar-no-aplica/
# ============================================================================

@csrf_exempt
@require_http_methods(['POST'])
def marcar_no_aplica(request, contacto_id: int):
    """Teléfono inválido, falleció, etc. Setea gracia de 90 días en Cliente."""
    err = _require_api_key(request)
    if err:
        return err

    import json
    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Body must be JSON'}, status=400)

    try:
        contacto = ContactoWhatsApp.objects.select_related('cliente').get(id=contacto_id)
    except ContactoWhatsApp.DoesNotExist:
        return JsonResponse({'error': 'ContactoWhatsApp no existe'}, status=404)

    if contacto.estado != 'pendiente':
        return JsonResponse(
            {'error': f'Contacto en estado {contacto.estado!r}'},
            status=400,
        )

    razon = (body.get('razon') or '').strip()
    operador = (body.get('operador') or '').strip()

    contacto.estado = 'no_aplica'
    contacto.operador = operador
    contacto.nota_operador = razon
    contacto.save(update_fields=['estado', 'operador', 'nota_operador'])

    # Gracia 90 días en Cliente
    contacto.cliente.proximo_contacto_no_antes_de = (
        timezone.now().date() + timedelta(days=GRACIA_NO_APLICA)
    )
    contacto.cliente.save(update_fields=['proximo_contacto_no_antes_de'])

    return JsonResponse({'success': True, 'contacto_id': contacto.id})


# ============================================================================
# 5. POST bandeja-whatsapp/<id>/registrar-respuesta/
# ============================================================================

@csrf_exempt
@require_http_methods(['POST'])
def registrar_respuesta(request, contacto_id: int):
    """Operador registra la respuesta del cliente a un mensaje ya enviado.

    Body JSON:
        {
            "respondio": true,
            "tipo_respuesta": "interesado" | "reservo" | "consulto_precio" |
                              "mas_adelante" | "rechazo" | "opt_out" |
                              "sin_respuesta",
            "nota_operador": "...",
            "operador": "deborah"
        }

    Side effects según tipo_respuesta:
        - 'opt_out'      → Cliente.opt_out_whatsapp = True
        - 'mas_adelante' → Cliente.proximo_contacto_no_antes_de = today + 60d
        - 'reservo'      → la atribución la hace el cron nocturno de Etapa 6,
                           acá solo registramos la respuesta
    """
    import json

    err = _require_api_key(request)
    if err:
        return err

    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Body must be JSON'}, status=400)

    try:
        contacto = ContactoWhatsApp.objects.select_related('cliente').get(id=contacto_id)
    except ContactoWhatsApp.DoesNotExist:
        return JsonResponse({'error': 'ContactoWhatsApp no existe'}, status=404)

    if contacto.estado != 'enviado':
        return JsonResponse(
            {'error': f'Solo se pueden registrar respuestas en contactos enviados '
                      f'(actual: {contacto.estado!r})'},
            status=400,
        )

    tipo_respuesta = (body.get('tipo_respuesta') or '').strip()
    validos = {choice[0] for choice in ContactoWhatsApp.TIPO_RESPUESTA_CHOICES}
    if tipo_respuesta not in validos:
        return JsonResponse(
            {'error': f'tipo_respuesta inválido: {tipo_respuesta!r}',
             'validos': sorted(validos)},
            status=400,
        )

    contacto.respondio = bool(body.get('respondio', True))
    contacto.tipo_respuesta = tipo_respuesta
    contacto.fecha_respuesta = timezone.now()
    contacto.nota_operador = (body.get('nota_operador') or '').strip()
    if body.get('operador'):
        contacto.operador = body['operador'].strip()
    contacto.save(update_fields=[
        'respondio', 'tipo_respuesta', 'fecha_respuesta', 'nota_operador', 'operador',
    ])

    # Side effects en Cliente según tipo_respuesta
    cliente_actualizado = False
    if tipo_respuesta == 'opt_out':
        contacto.cliente.opt_out_whatsapp = True
        contacto.cliente.save(update_fields=['opt_out_whatsapp'])
        cliente_actualizado = True
    elif tipo_respuesta == 'mas_adelante':
        contacto.cliente.proximo_contacto_no_antes_de = (
            timezone.now().date() + timedelta(days=GRACIA_MAS_ADELANTE)
        )
        contacto.cliente.save(update_fields=['proximo_contacto_no_antes_de'])
        cliente_actualizado = True

    return JsonResponse({
        'success': True,
        'contacto_id': contacto.id,
        'cliente_actualizado': cliente_actualizado,
    })


# ============================================================================
# 6. GET bandeja-whatsapp/explicacion/<id>/  (STUB)
# ============================================================================

@csrf_exempt
@require_http_methods(['GET'])
def explicacion(request, contacto_id: int):
    """STUB Etapa 4: devuelve string vacío.

    La integración con LLM (Gemini Flash Lite vía OpenRouter) se hace en
    Etapa futura. Mientras tanto el frontend muestra el placeholder vacío
    o un fallback estático.
    """
    err = _require_api_key(request)
    if err:
        return err

    if not ContactoWhatsApp.objects.filter(id=contacto_id).exists():
        return JsonResponse({'error': 'ContactoWhatsApp no existe'}, status=404)

    return JsonResponse({
        'contacto_id': contacto_id,
        'explicacion': '',
        'fuente': 'stub',
    })


# ============================================================================
# 7. GET bandeja-whatsapp/resumen-dia/?fecha=YYYY-MM-DD
# ============================================================================

@csrf_exempt
@require_http_methods(['GET'])
def resumen_dia(request):
    """Resumen de actividad de un día específico + acumulado semanal."""
    err = _require_api_key(request)
    if err:
        return err

    fecha_obj = _parse_fecha(request.GET.get('fecha')) or timezone.now().date()
    return JsonResponse(_build_resumen_dia(fecha_obj))


def _build_resumen_dia(fecha_obj: date) -> dict:
    """Compila stats del día + semana ISO de esa fecha."""
    qs_dia = ContactoWhatsApp.objects.filter(fecha_sugerido=fecha_obj)
    enviados = qs_dia.filter(estado='enviado').count()
    omitidos = qs_dia.filter(estado='omitido').count()
    no_aplica = qs_dia.filter(estado='no_aplica').count()

    # Tiempo total ≈ max(fecha_envio) - min(fecha_envio) del día
    tiempo_min = 0
    fechas_envio = list(
        qs_dia.filter(estado='enviado', fecha_envio__isnull=False)
        .values_list('fecha_envio', flat=True)
        .order_by('fecha_envio')
    )
    if len(fechas_envio) >= 2:
        delta = fechas_envio[-1] - fechas_envio[0]
        tiempo_min = int(delta.total_seconds() // 60)

    # Operador del día (cualquiera que aparezca; en MVP es 'deborah')
    operador = (
        qs_dia.filter(estado='enviado')
        .values_list('operador', flat=True)
        .first() or ''
    )

    # Stats semana ISO de esa fecha (lunes a domingo)
    iso_year, iso_week, _ = fecha_obj.isocalendar()
    # Calcular el lunes y domingo de esa semana
    lunes = fecha_obj - timedelta(days=fecha_obj.weekday())
    domingo = lunes + timedelta(days=6)
    qs_semana = ContactoWhatsApp.objects.filter(
        fecha_sugerido__gte=lunes, fecha_sugerido__lte=domingo,
    )
    enviados_sem = qs_semana.filter(estado='enviado').count()
    respondieron_sem = qs_semana.filter(estado='enviado').exclude(tipo_respuesta='').count()
    convirtieron_sem = qs_semana.filter(convirtio=True).count()
    ingreso_sem = qs_semana.filter(
        convirtio=True, reserva_atribuida__isnull=False,
    ).aggregate(total=Sum('reserva_atribuida__total'))['total'] or 0

    return {
        'fecha': fecha_obj.isoformat(),
        'operador': operador,
        'enviados': enviados,
        'omitidos': omitidos,
        'no_aplica': no_aplica,
        'tiempo_total_minutos': tiempo_min,
        'semana_actual': {
            'iso_year': iso_year,
            'iso_week': iso_week,
            'desde': lunes.isoformat(),
            'hasta': domingo.isoformat(),
            'mensajes_enviados': enviados_sem,
            'respuestas_recibidas': respondieron_sem,
            'tasa_respuesta': (
                round(respondieron_sem / enviados_sem, 3) if enviados_sem else 0.0
            ),
            'reservas_atribuidas': convirtieron_sem,
            'ingreso_atribuido': int(ingreso_sem),
        },
    }


# ============================================================================
# 8. GET movimientos/?desde=YYYY-MM-DD&hasta=YYYY-MM-DD
# ============================================================================

@csrf_exempt
@require_http_methods(['GET'])
def movimientos(request):
    """Matriz de movimientos de taxonomía + atribución a WhatsApp."""
    err = _require_api_key(request)
    if err:
        return err

    hoy = timezone.now().date()
    desde = _parse_fecha(request.GET.get('desde')) or (hoy - timedelta(days=30))
    hasta = _parse_fecha(request.GET.get('hasta')) or hoy

    qs = TaxonomiaMovimiento.objects.filter(fecha__gte=desde, fecha__lte=hasta)

    positivos = 0
    negativos = 0
    atribuidos = 0
    matriz_dict = {}  # key: (antes, despues) → cantidad + atribuidos
    por_dia = {}

    for mov in qs.iterator():
        antes_orden = ORDEN_VALOR.get(mov.eje_valor_antes, 99)
        despues_orden = ORDEN_VALOR.get(mov.eje_valor_despues, 99)
        es_positivo = despues_orden < antes_orden  # menor índice = mejor
        es_negativo = despues_orden > antes_orden

        if es_positivo:
            positivos += 1
        elif es_negativo:
            negativos += 1

        if mov.contacto_whatsapp_atribuido_id is not None:
            atribuidos += 1

        key = (mov.eje_valor_antes, mov.eje_valor_despues)
        if key not in matriz_dict:
            matriz_dict[key] = {'cantidad': 0, 'atribuidos_whatsapp': 0}
        matriz_dict[key]['cantidad'] += 1
        if mov.contacto_whatsapp_atribuido_id is not None:
            matriz_dict[key]['atribuidos_whatsapp'] += 1

        f_iso = mov.fecha.isoformat()
        if f_iso not in por_dia:
            por_dia[f_iso] = {'positivos': 0, 'negativos': 0}
        if es_positivo:
            por_dia[f_iso]['positivos'] += 1
        elif es_negativo:
            por_dia[f_iso]['negativos'] += 1

    matriz_list = sorted(
        [
            {'antes': k[0], 'despues': k[1], **v}
            for k, v in matriz_dict.items()
        ],
        key=lambda x: -x['cantidad'],
    )
    por_dia_list = sorted(
        [{'fecha': k, **v} for k, v in por_dia.items()],
        key=lambda x: x['fecha'],
    )

    return JsonResponse({
        'periodo': {'desde': desde.isoformat(), 'hasta': hasta.isoformat()},
        'totales': {
            'positivos': positivos,
            'negativos': negativos,
            'saldo_neto': positivos - negativos,
            'atribuidos_whatsapp': atribuidos,
        },
        'matriz_eje_valor': matriz_list,
        'movimientos_por_dia': por_dia_list,
    })


# ============================================================================
# 9. GET scripts-estadisticas/?desde=YYYY-MM-DD&hasta=YYYY-MM-DD
# ============================================================================

@csrf_exempt
@require_http_methods(['GET'])
def scripts_estadisticas(request):
    """Performance de cada plantilla en un período: enviados, respuestas,
    conversiones, ingreso atribuido."""
    err = _require_api_key(request)
    if err:
        return err

    hoy = timezone.now().date()
    desde = _parse_fecha(request.GET.get('desde')) or (hoy - timedelta(days=30))
    hasta = _parse_fecha(request.GET.get('hasta')) or hoy

    out = []
    for script in ScriptWhatsApp.objects.all().order_by('script_id'):
        qs = ContactoWhatsApp.objects.filter(
            script=script,
            fecha_envio__date__gte=desde,
            fecha_envio__date__lte=hasta,
            estado__in=['enviado'],
        )
        enviados = qs.count()
        if enviados == 0:
            continue  # no incluir scripts sin uso en el período

        respondieron = qs.exclude(tipo_respuesta='').count()
        reservaron = qs.filter(convirtio=True).count()
        ingreso = qs.filter(
            convirtio=True, reserva_atribuida__isnull=False,
        ).aggregate(total=Sum('reserva_atribuida__total'))['total'] or 0

        out.append({
            'script_id': script.script_id,
            'nombre': script.nombre,
            'enviados': enviados,
            'respondieron': respondieron,
            'tasa_respuesta': round(respondieron / enviados, 3),
            'reservaron': reservaron,
            'tasa_conversion': round(reservaron / enviados, 3),
            'ingreso_atribuido': int(ingreso),
        })

    return JsonResponse({
        'periodo': {'desde': desde.isoformat(), 'hasta': hasta.isoformat()},
        'scripts': out,
    })


# ============================================================================
# Etapa 5.5.2 — POST bandeja-whatsapp/<id>/bloquear-cliente/
# ============================================================================

@csrf_exempt
@require_http_methods(['POST'])
def bloquear_cliente(request, contacto_id: int):
    """Bloquea PERMANENTEMENTE al cliente para no recibir más WhatsApp.

    Disparado por el botón "No volver a contactar" en la bandeja cuando el
    operador detecta que el destinatario es staff/proxy/fallecido/etc.

    Body JSON:
        {
            "operador": "jorge",
            "razon": "cliente proxy - staff"
        }

    Side effects:
        - Cliente.opt_out_whatsapp = True (bloqueo permanente, sin gracia)
        - Si el contacto está en 'pendiente', se marca como 'no_aplica' con
          nota_operador = razón (preserva auditoría)
        - Log INFO con operador + razón + cliente_id

    Idempotente:
        Si el cliente ya está bloqueado, devuelve 200 con cliente_bloqueado=False
        (no estaba sin bloqueo, nada nuevo que hacer), pero igual marca el
        contacto como no_aplica si está pendiente.
    """
    import json

    err = _require_api_key(request)
    if err:
        return err

    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Body must be JSON'}, status=400)

    try:
        contacto = ContactoWhatsApp.objects.select_related('cliente').get(id=contacto_id)
    except ContactoWhatsApp.DoesNotExist:
        return JsonResponse({'error': 'ContactoWhatsApp no existe'}, status=404)

    if contacto.cliente is None:
        return JsonResponse(
            {'error': 'Contacto sin cliente asociado — no se puede bloquear'},
            status=400,
        )

    razon = (body.get('razon') or '').strip()
    operador = (body.get('operador') or '').strip()

    # Bloquear cliente (idempotente)
    cliente_bloqueado = False
    if not contacto.cliente.opt_out_whatsapp:
        contacto.cliente.opt_out_whatsapp = True
        contacto.cliente.save(update_fields=['opt_out_whatsapp'])
        cliente_bloqueado = True

    # Actualizar contacto pendiente (también idempotente)
    contacto_actualizado = False
    if contacto.estado == 'pendiente':
        contacto.estado = 'no_aplica'
        if operador:
            contacto.operador = operador
        if razon:
            contacto.nota_operador = razon
        contacto.save(update_fields=['estado', 'operador', 'nota_operador'])
        contacto_actualizado = True

    logger.info(
        "Bloqueo manual cliente_id=%s por operador=%r razon=%r "
        "(cliente_bloqueado=%s, contacto_actualizado=%s)",
        contacto.cliente_id, operador, razon,
        cliente_bloqueado, contacto_actualizado,
    )

    return JsonResponse({
        'success': True,
        'cliente_id': contacto.cliente_id,
        'cliente_bloqueado': cliente_bloqueado,
        'contacto_id': contacto.id,
        'contacto_actualizado': contacto_actualizado,
    })


# ============================================================================
# Etapa 5.6 — GET bandeja-whatsapp/del-dia/
# ============================================================================
# Historial del día: lista de TODOS los contactos del día (procesados +
# pendientes) para que el operador pueda "deshacer" o reaccionar a casos
# que detectó después (ej. cliente respondió por WhatsApp tarde).


# Cap del query param `limit` para proteger el server de queries gigantes.
DEL_DIA_LIMIT_MAX = 500
DEL_DIA_LIMIT_DEFAULT = 100

# Estados considerados "procesados" (tienen operador asociado).
ESTADOS_PROCESADOS = ('enviado', 'omitido', 'no_aplica', 'descartado')


def _serializar_contacto_historial(c: ContactoWhatsApp) -> dict:
    """Versión del serializador con TODOS los campos relevantes para historial.

    Extiende _serializar_contacto agregando:
      - mensaje_enviado_editado (si el operador editó el texto)
      - fecha_envio, operador
      - respondio, tipo_respuesta, nota_operador
      - cliente_opt_out_actual (estado actual del Cliente.opt_out_whatsapp,
        NO del snapshot — clave para que el frontend sepa si el botón
        "Bloquear permanente" ya está cumplido)
    """
    base = _serializar_contacto(c)
    base.update({
        'mensaje_enviado_editado': c.mensaje_enviado_editado or '',
        'fecha_envio': c.fecha_envio.isoformat() if c.fecha_envio else None,
        'operador': c.operador or '',
        'respondio': bool(c.respondio),
        'tipo_respuesta': c.tipo_respuesta or '',
        'nota_operador': c.nota_operador or '',
        'cliente_opt_out_actual': (
            bool(c.cliente.opt_out_whatsapp) if c.cliente else False
        ),
    })
    return base


@csrf_exempt
@require_http_methods(['GET'])
def del_dia(request):
    """Devuelve TODOS los contactos del día (procesados + pendientes).

    Query params:
        fecha=YYYY-MM-DD   (opcional, default: hoy zona horaria Santiago)
        operador=jorge     (opcional, filtra solo procesados de ese operador)
        limit=100          (opcional, default 100, max 500)

    Reglas de filtrado:
        - Sin operador: devuelve TODOS los contactos del día (procesados +
          pendientes) sin importar quién los procesó.
        - Con operador: devuelve SOLO contactos procesados (enviado/omitido/
          no_aplica/descartado) cuyo operador coincide. NO incluye pendientes
          (los pendientes aún no tienen operador asociado, no tendría sentido
          filtrar por uno).

    Orden:
        1. Procesados primero, por fecha_envio DESC (más reciente arriba —
           útil para "deshacer última acción").
        2. Pendientes después, por prioridad ASC, gasto_historico_snapshot DESC
           (sin operador filter — los pendientes no entran si hay operador).
    """
    err = _require_api_key(request)
    if err:
        return err

    # ---- Parse fecha ----
    fecha_str = request.GET.get('fecha')
    if fecha_str:
        fecha_obj = _parse_fecha(fecha_str)
        if fecha_obj is None:
            return JsonResponse(
                {'error': f'Parámetro fecha inválido: {fecha_str!r}. Formato YYYY-MM-DD.'},
                status=400,
            )
    else:
        fecha_obj = timezone.localtime(timezone.now()).date()

    # ---- Parse limit ----
    try:
        limit = int(request.GET.get('limit', DEL_DIA_LIMIT_DEFAULT))
    except (TypeError, ValueError):
        limit = DEL_DIA_LIMIT_DEFAULT
    limit = max(1, min(limit, DEL_DIA_LIMIT_MAX))

    # ---- Parse operador ----
    operador_filtro = (request.GET.get('operador') or '').strip() or None

    # ---- Query base: contactos del día ----
    qs_base = (
        ContactoWhatsApp.objects
        .select_related('cliente', 'cliente__taxonomia', 'script')
        .filter(fecha_sugerido=fecha_obj)
    )

    # ---- Aplicar filtros según presencia de operador ----
    if operador_filtro:
        # Solo procesados de ese operador (los pendientes no tienen operador)
        qs_visibles = qs_base.filter(
            estado__in=ESTADOS_PROCESADOS,
            operador=operador_filtro,
        )
    else:
        # Todo el día (procesados + pendientes)
        qs_visibles = qs_base

    # ---- Stats ANTES de aplicar limit ----
    stats = {
        'enviados': 0,
        'omitidos': 0,
        'no_aplica': 0,
        'pendientes': 0,
        'descartados': 0,
    }
    # Una sola query agregando por estado
    from django.db.models import Count
    estado_counts = dict(
        qs_visibles.values_list('estado').annotate(n=Count('id')).values_list('estado', 'n')
    )
    stats['enviados'] = estado_counts.get('enviado', 0)
    stats['omitidos'] = estado_counts.get('omitido', 0)
    stats['no_aplica'] = estado_counts.get('no_aplica', 0)
    stats['pendientes'] = estado_counts.get('pendiente', 0)
    stats['descartados'] = estado_counts.get('descartado', 0)
    total = sum(stats.values())

    # ---- Ordenar y materializar ----
    # Para combinar "procesados por fecha_envio DESC" + "pendientes por prioridad ASC",
    # hacemos 2 querysets y los concatenamos en Python.
    qs_procesados = (
        qs_visibles
        .filter(estado__in=ESTADOS_PROCESADOS, fecha_envio__isnull=False)
        .order_by('-fecha_envio', '-id')
    )
    qs_pendientes = (
        qs_visibles
        .filter(estado='pendiente')
        .order_by('prioridad', '-gasto_historico_snapshot', 'id')
    )

    # Materializar respetando limit total
    procesados_list = list(qs_procesados[:limit])
    restantes = max(0, limit - len(procesados_list))
    pendientes_list = list(qs_pendientes[:restantes]) if restantes else []
    ordenados = procesados_list + pendientes_list

    contactos_data = [_serializar_contacto_historial(c) for c in ordenados]

    return JsonResponse({
        'fecha': fecha_obj.isoformat(),
        'operador_filtro': operador_filtro or '',
        'total': total,
        'stats': stats,
        'limit_aplicado': limit,
        'contactos': contactos_data,
    })
