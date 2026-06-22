"""WhatsApp Cloud API — endpoints de persistencia (consumidos por aremko-cli / Go).

Auth: header X-API-Key (LUNA_API_KEY), mismo esquema que la bandeja OVC.
Rutas:
  POST /api/whatsapp/inbound        → guarda entrante, matchea/crea cliente, marca OVC
  POST /api/whatsapp/inbound-media  → entrante con adjunto (foto/PDF/voz/video)
  POST /api/whatsapp/outbound       → guarda saliente ligado al cliente
  POST /api/whatsapp/outbound-media → saliente con adjunto (foto/PDF/audio/video)
  GET  /api/whatsapp/conversation/  → historial (in+out) por teléfono
  GET  /api/whatsapp/conversations/ → lista de conversaciones (una fila por teléfono)
  POST /api/whatsapp/conversations/<phone>/marcar-atendido/ → saca de la cola de pendientes
  GET  /api/whatsapp/pending-template-sends → bandeja salva 1 lista para plantilla Meta
  POST /api/whatsapp/mark-template-sent     → Go confirma envío de plantilla
  POST /api/whatsapp/mark-template-failed   → Go reporta fallo de envío
"""

import json
import os
import uuid
import mimetypes
from datetime import datetime, timedelta, timezone as dt_tz

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt

from ..models import WhatsAppMessage, ContactoWhatsApp, Cliente
from inbox_omnicanal.views import _propuesta_reserva  # H-028 FIX: agregar propuesta al endpoint


def _check_luna_key(request):
    """Auth alineada con /api/refugio-leads/summary/: valida X-API-Key contra
    settings.LUNA_API_KEY (NO AUTOMATION_API_KEY). Header case-insensitive.
    Devuelve None si OK, o JsonResponse 401 si falta/es inválida."""
    expected = getattr(settings, 'LUNA_API_KEY', None)
    # request.headers es case-insensitive (X-Api-Key == X-API-Key); META como respaldo.
    provided = request.headers.get('X-API-Key') or request.META.get('HTTP_X_API_KEY')
    if not expected or not provided or provided != expected:
        return JsonResponse({'error': 'No autorizado. Se requiere header X-API-Key válido.'}, status=401)
    return None


def _parse_ts(value):
    """Acepta epoch (seg) o ISO; devuelve datetime aware. Default: ahora."""
    if value in (None, ''):
        return timezone.now()
    try:
        return datetime.fromtimestamp(int(float(value)), tz=dt_tz.utc)
    except (ValueError, TypeError, OSError):
        pass
    parsed = parse_datetime(str(value))
    if parsed:
        return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed, dt_tz.utc)
    return timezone.now()


def _ventana_24h(ts):
    """Fin de la ventana de servicio de 24h (ISO 8601)."""
    return (ts + timedelta(hours=24)).isoformat()


def _match_or_create_cliente(phone, nombre=''):
    """Matchea Cliente por teléfono; si no existe, lo crea. Devuelve Cliente o None."""
    from ..services.cliente_service import ClienteService
    try:
        cliente, normalizado = ClienteService.buscar_cliente_por_telefono(phone)
    except Exception:
        cliente, normalizado = None, None
    if cliente:
        if nombre and not cliente.nombre:
            cliente.nombre = nombre[:100]
            cliente.save(update_fields=['nombre'])
        return cliente
    try:
        return Cliente.objects.create(
            nombre=(nombre or f"WhatsApp {phone}")[:100],
            telefono=(normalizado or phone)[:20],
        )
    except Exception:
        try:
            cliente, _ = ClienteService.buscar_cliente_por_telefono(phone)
            return cliente
        except Exception:
            return None


def _link_contacto_ovc(cliente, msg, ts):
    """Bandeja OVC: marca el contacto activo del cliente como 'respondió' y lo
    enlaza al mensaje. Devuelve el ContactoWhatsApp o None. Compartido por los
    entrantes de texto y de media."""
    if not cliente:
        return None
    contacto = (
        ContactoWhatsApp.objects
        .filter(cliente=cliente, estado__in=['enviado', 'pendiente'])
        .order_by('-fecha_envio', '-fecha_sugerido')
        .first()
    )
    if contacto:
        if not contacto.respondio:
            contacto.respondio = True
            contacto.fecha_respuesta = ts
            contacto.save(update_fields=['respondio', 'fecha_respuesta'])
        msg.contacto_whatsapp = contacto
        msg.save(update_fields=['contacto_whatsapp'])
    return contacto


def _media_label(msg_type, original_filename=''):
    """Etiqueta de preview para un adjunto sin caption (lista de conversaciones)."""
    t = (msg_type or '').lower()
    if t == 'image':
        return '📷 Foto'
    if t == 'video':
        return '🎥 Video'
    if t in ('audio', 'voice'):
        return '🎤 Nota de voz'
    if t == 'document':
        nombre = (original_filename or '').strip()
        return f'📄 {nombre}' if nombre else '📄 Documento'
    if t == 'sticker':
        return '🟢 Sticker'
    return ''


def _guess_extension(original_filename, mime_type):
    """Extensión del archivo: primero del nombre original, luego del mime_type."""
    _, ext = os.path.splitext(original_filename or '')
    if ext:
        return ext[:12]
    guessed = mimetypes.guess_extension((mime_type or '').split(';')[0].strip())
    return guessed or ''


def _media_url(request, msg):
    """URL absoluta del adjunto (el frontend vive en otro dominio). Si el storage
    ya devuelve una URL absoluta (Cloudinary), build_absolute_uri la deja igual."""
    if not msg.media_file:
        return None
    try:
        return request.build_absolute_uri(msg.media_file.url)
    except Exception:
        return None


@csrf_exempt
def inbound(request):
    err = _check_luna_key(request)
    if err:
        return err
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, TypeError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    wa_id = (data.get('wa_message_id') or '').strip()
    phone = (data.get('from') or '').strip()
    if not wa_id or not phone:
        return JsonResponse({'error': 'wa_message_id y from son obligatorios'}, status=400)

    body = data.get('body') or ''
    msg_type = (data.get('type') or 'text')[:30]
    contact_name = (data.get('contact_name') or '')[:160]
    ts = _parse_ts(data.get('timestamp'))

    # Idempotencia por wa_message_id
    existing = WhatsAppMessage.objects.filter(wa_message_id=wa_id).first()
    if existing:
        return JsonResponse({
            'ok': True, 'idempotent': True, 'message_id': existing.id,
            'cliente_id': existing.cliente_id, 'contacto_id': existing.contacto_whatsapp_id,
            'ventana_24h_hasta': _ventana_24h(existing.timestamp),
        })

    cliente = _match_or_create_cliente(phone, contact_name)

    # Una reacción (❤️, 👍, …) no exige respuesta del operador → no la pone en
    # la cola de pendientes. El resto de los entrantes sí. (H-005)
    requiere = msg_type != 'reaction'

    msg = WhatsAppMessage.objects.create(
        cliente=cliente, direction='in', wa_message_id=wa_id, phone=phone[:20],
        body=body, msg_type=msg_type, timestamp=ts, status='received',
        contact_name=contact_name, requiere_atencion=requiere,
    )

    # Bandeja OVC: marcar el contacto del cliente como "respondió" (respuesta pendiente
    # de atención por el operador). Reusa el flag respondio/fecha_respuesta existente.
    contacto = _link_contacto_ovc(cliente, msg, ts)

    return JsonResponse({
        'ok': True,
        'message_id': msg.id,
        'cliente_id': cliente.id if cliente else None,
        'contacto_id': contacto.id if contacto else None,
        # True si hay cliente pero NO había contacto OVC activo: el operador debe
        # atender el entrante (queda como requiere_atencion en WhatsAppMessage).
        'requiere_atencion_sin_contacto': bool(cliente and not contacto),
        'ventana_24h_hasta': _ventana_24h(ts),
        # H-008: si el "mensaje de ausencia" está activo, directiva para que el Go de
        # aremko-cli auto-responda la frase fija (con guard anti-spam). null si no
        # aplica. Solo para entrantes de texto (no reacciones).
        'responder_ausencia': _directiva_ausencia(phone, msg_type),
        # H-037 (Luna Interna): si el entrante es de staff whitelisted y es un inicio
        # de turno → directiva {responde_auto, texto, sugerencia_id} para que Go envíe
        # el briefing SOLO (sin cajón). null si no aplica. Solo cálculo determinístico
        # (NO genera el borrador LLM del cliente → cero costo extra en entrantes).
        'responder_briefing': _directiva_briefing_staff(phone, body, msg_type, wa_id),
    })


def _directiva_ausencia(phone, msg_type):
    """Devuelve {'mensaje': texto} si toca auto-responder ausencia, o None. Nunca rompe el inbound."""
    if msg_type == 'reaction':
        return None
    try:
        from whatsapp_agent.agent import get_config
        from whatsapp_agent.ausencia import evaluar_ausencia
        mensaje = evaluar_ausencia(get_config(), phone)
        return {'mensaje': mensaje} if mensaje else None
    except Exception:  # noqa: BLE001 — la ausencia es opcional; jamás tumbar el inbound
        import logging
        logging.getLogger(__name__).exception('Ausencia: fallo evaluando para %s', phone)
        return None


def _directiva_briefing_staff(phone, body, msg_type, wa_id):
    """H-037 (Luna Interna): directiva de auto-respuesta para el webhook de aremko-cli.

    Si el entrante es de un número STAFF whitelisted (PersonalOperativo.responde_auto)
    y es un inicio de turno ("empezando el día"/saludo) → devuelve
    {'responde_auto': True, 'texto': <briefing>, 'sugerencia_id': wa_id} para que Go lo
    envíe SOLO (sin cajón). None en cualquier otro caso (cliente, o staff sin trigger).

    Determinístico: NO invoca el LLM → no genera borradores de cliente anticipados ni
    gasto extra. Nunca rompe el inbound.
    """
    if msg_type == 'reaction':
        return None
    try:
        if not _es_inicio_turno(body or ''):
            return None
        from personal_operativo.services import buscar_personal, construir_briefing
        persona = buscar_personal(phone)
        if not persona or not persona.responde_auto:
            return None
        return {
            'responde_auto': True,
            'texto': construir_briefing(persona),
            'sugerencia_id': wa_id,
        }
    except Exception:  # noqa: BLE001 — jamás tumbar el inbound
        import logging
        logging.getLogger(__name__).exception('Briefing staff (inbound) falló para %s', phone)
        return None


# Tipos de mensaje con adjunto que aceptamos.
_MEDIA_TYPES = {'image', 'video', 'audio', 'voice', 'document', 'sticker'}

# Tope de tamaño de adjunto. 16 MB = límite de la Cloud API para video/audio (cubre
# también imagen 5 MB y voz). Configurable por settings.WHATSAPP_MEDIA_MAX_BYTES.
# El lado Go también limita.
_MEDIA_MAX_BYTES_DEFAULT = 16 * 1024 * 1024


@csrf_exempt
def inbound_media(request):
    """POST /api/whatsapp/inbound-media (multipart/form-data) — entrante con adjunto.

    aremko-cli descarga los bytes de la Cloud API (con el token) y nos los sube acá.
    Guardamos el archivo (nombre UUID, no el del cliente) y creamos el WhatsAppMessage.
    Idempotente por wa_message_id.
    """
    err = _check_luna_key(request)
    if err:
        return err
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    wa_id = (request.POST.get('wa_message_id') or '').strip()
    phone = (request.POST.get('from') or '').strip()
    if not wa_id or not phone:
        return JsonResponse({'error': 'wa_message_id y from son obligatorios'}, status=400)

    upload = request.FILES.get('file')
    if not upload:
        return JsonResponse({'error': "Falta el archivo 'file' (multipart/form-data)"}, status=400)

    # Tope de tamaño: rechaza antes de subir a Cloudinary (evita el error de storage).
    max_bytes = int(getattr(settings, 'WHATSAPP_MEDIA_MAX_BYTES', _MEDIA_MAX_BYTES_DEFAULT))
    size = getattr(upload, 'size', 0) or 0
    if size > max_bytes:
        return JsonResponse({
            'error': 'Archivo demasiado grande',
            'max_bytes': max_bytes,
            'max_mb': round(max_bytes / (1024 * 1024), 1),
            'size_bytes': size,
        }, status=413)

    msg_type = (request.POST.get('type') or 'document').lower()[:30]
    if msg_type not in _MEDIA_TYPES:
        msg_type = 'document'
    caption = request.POST.get('caption') or ''
    mime_type = (request.POST.get('mime_type') or getattr(upload, 'content_type', '') or '')[:120]
    original_filename = (request.POST.get('filename') or getattr(upload, 'name', '') or '')[:255]
    contact_name = (request.POST.get('contact_name') or '')[:160]
    ts = _parse_ts(request.POST.get('timestamp'))

    # Idempotencia por wa_message_id
    existing = WhatsAppMessage.objects.filter(wa_message_id=wa_id).first()
    if existing:
        return JsonResponse({
            'success': True, 'idempotent': True,
            'wa_message_id': wa_id,
            'message_id': existing.id,
            'cliente_id': existing.cliente_id,
            'media_url': _media_url(request, existing),
        })

    cliente = _match_or_create_cliente(phone, contact_name)

    # Nombre con UUID + extensión (evita colisiones y path traversal del nombre del cliente).
    ext = _guess_extension(original_filename, mime_type)
    stored_name = f"{uuid.uuid4().hex}{ext}"

    msg = WhatsAppMessage(
        cliente=cliente, direction='in', wa_message_id=wa_id, phone=phone[:20],
        body=caption, msg_type=msg_type, timestamp=ts, status='received',
        contact_name=contact_name, requiere_atencion=True,
        mime_type=mime_type, original_filename=original_filename,
    )
    # upload_to='whatsapp/' antepone la carpeta; save=False para persistir una sola vez.
    msg.media_file.save(stored_name, upload, save=False)
    msg.save()

    _link_contacto_ovc(cliente, msg, ts)

    return JsonResponse({
        'success': True,
        'wa_message_id': wa_id,
        'message_id': msg.id,
        'cliente_id': cliente.id if cliente else None,
        'media_url': _media_url(request, msg),
    })


@csrf_exempt
def outbound(request):
    err = _check_luna_key(request)
    if err:
        return err
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, TypeError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    wa_id = (data.get('wa_message_id') or '').strip()
    phone = (data.get('to') or '').strip()
    if not wa_id or not phone:
        return JsonResponse({'error': 'wa_message_id y to son obligatorios'}, status=400)

    body = data.get('body') or ''
    ts = _parse_ts(data.get('timestamp'))

    existing = WhatsAppMessage.objects.filter(wa_message_id=wa_id).first()
    if existing:
        return JsonResponse({'ok': True, 'idempotent': True, 'message_id': existing.id,
                             'cliente_id': existing.cliente_id})

    cliente = _match_or_create_cliente(phone)

    msg = WhatsAppMessage.objects.create(
        cliente=cliente, direction='out', wa_message_id=wa_id, phone=phone[:20],
        body=body, msg_type='text', timestamp=ts, status='sent',
    )

    # H-008: el mensaje de ausencia se persiste pero NO debe sacar la conversación de
    # "pendientes" (Deborah debe verlas al volver). El Go lo manda con no_marcar_atendido.
    marcar = not _truthy(data.get('no_marcar_atendido'))
    _outbound_side_effects(cliente, phone, ts, marcar_atendido=marcar)

    return JsonResponse({'ok': True, 'message_id': msg.id,
                         'cliente_id': cliente.id if cliente else None})


def _outbound_side_effects(cliente, phone, ts, marcar_atendido=True):
    """Efectos comunes de un saliente: registrar último contacto (anti-saturación
    de la bandeja) y, salvo `marcar_atendido=False`, limpiar la cola de pendientes
    (responder = atender)."""
    if cliente:
        try:
            cliente.ultimo_contacto_outbound = ts.date()
            cliente.save(update_fields=['ultimo_contacto_outbound'])
        except Exception:
            pass
    if not marcar_atendido:
        return
    try:
        WhatsAppMessage.objects.filter(
            phone=phone[:20], direction='in', requiere_atencion=True,
        ).update(requiere_atencion=False)
    except Exception:
        pass


@csrf_exempt
def outbound_media(request):
    """POST /api/whatsapp/outbound-media (multipart/form-data) — saliente con adjunto.

    Guarda el MISMO archivo que se envió por la Cloud API para mostrarlo en el hilo.
    Idempotente por wa_message_id. No marca requiere_atencion (es saliente).
    """
    err = _check_luna_key(request)
    if err:
        return err
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    wa_id = (request.POST.get('wa_message_id') or '').strip()
    phone = (request.POST.get('to') or '').strip()
    if not wa_id or not phone:
        return JsonResponse({'error': 'wa_message_id y to son obligatorios'}, status=400)

    upload = request.FILES.get('file')
    if not upload:
        return JsonResponse({'error': "Falta el archivo 'file' (multipart/form-data)"}, status=400)

    max_bytes = int(getattr(settings, 'WHATSAPP_MEDIA_MAX_BYTES', _MEDIA_MAX_BYTES_DEFAULT))
    size = getattr(upload, 'size', 0) or 0
    if size > max_bytes:
        return JsonResponse({
            'error': 'Archivo demasiado grande',
            'max_bytes': max_bytes,
            'max_mb': round(max_bytes / (1024 * 1024), 1),
            'size_bytes': size,
        }, status=413)

    msg_type = (request.POST.get('type') or 'document').lower()[:30]
    if msg_type not in _MEDIA_TYPES:
        msg_type = 'document'
    caption = request.POST.get('caption') or ''
    mime_type = (request.POST.get('mime_type') or getattr(upload, 'content_type', '') or '')[:120]
    original_filename = (request.POST.get('filename') or getattr(upload, 'name', '') or '')[:255]
    ts = _parse_ts(request.POST.get('timestamp'))

    existing = WhatsAppMessage.objects.filter(wa_message_id=wa_id).first()
    if existing:
        return JsonResponse({
            'success': True, 'idempotent': True,
            'message_id': existing.id,
            'cliente_id': existing.cliente_id,
            'media_url': _media_url(request, existing),
        })

    cliente = _match_or_create_cliente(phone)

    ext = _guess_extension(original_filename, mime_type)
    stored_name = f"{uuid.uuid4().hex}{ext}"

    msg = WhatsAppMessage(
        cliente=cliente, direction='out', wa_message_id=wa_id, phone=phone[:20],
        body=caption, msg_type=msg_type, timestamp=ts, status='sent',
        mime_type=mime_type, original_filename=original_filename,
    )
    msg.media_file.save(stored_name, upload, save=False)
    msg.save()

    _outbound_side_effects(cliente, phone, ts)

    return JsonResponse({
        'success': True,
        'message_id': msg.id,
        'cliente_id': cliente.id if cliente else None,
        'media_url': _media_url(request, msg),
    })


def conversation(request):
    err = _check_luna_key(request)
    if err:
        return err
    phone = (request.GET.get('phone') or '').strip()
    if not phone:
        return JsonResponse({'error': 'phone requerido'}, status=400)
    try:
        limit = min(int(request.GET.get('limit', 50)), 500)
    except (ValueError, TypeError):
        limit = 50

    from django.db.models import Q
    from ..services.cliente_service import ClienteService
    try:
        cliente, _ = ClienteService.buscar_cliente_por_telefono(phone)
    except Exception:
        cliente = None

    filtro = Q(phone=phone)
    if cliente:
        filtro |= Q(cliente=cliente)

    # Últimos N en orden cronológico ascendente
    recientes = list(WhatsAppMessage.objects.filter(filtro).order_by('-timestamp')[:limit])
    recientes.reverse()

    # H-037 (Luna Interna): si el número es staff whitelisted y el último entrante
    # es un inicio de turno ("empezando el día"/saludo), la sugerencia es el briefing
    # DETERMINÍSTICO y se marca responde_auto=true para que aremko-cli lo envíe solo
    # (sin el cajón de aprobación). Para clientes, todo sigue igual (responde_auto=false).
    sug_briefing = _briefing_staff(phone, recientes)
    if sug_briefing is not None:
        sugerencia = sug_briefing
        responde_auto = True
    else:
        sugerencia = _sugerencia_agente(phone, request)
        responde_auto = False

    return JsonResponse({
        'phone': phone,
        'cliente_id': cliente.id if cliente else None,
        'count': len(recientes),
        'messages': [{
            'wa_message_id': m.wa_message_id,
            'direction': m.direction,
            'body': m.body,
            'type': m.msg_type,
            'status': m.status,
            'timestamp': m.timestamp.isoformat(),
            'media_url': _media_url(request, m),
            'mime_type': m.mime_type or None,
            'filename': m.original_filename or None,
        } for m in recientes],
        # H-007 F1: borrador sugerido por el agente IA para el último entrante sin
        # responder (null si el agente está apagado, no hay pendiente, o ?sugerencia=0).
        'sugerencia_agente': sugerencia,
        # H-037: si true, aremko-cli envía la sugerencia AUTOMÁTICAMENTE (staff), sin cajón.
        'responde_auto': responde_auto,
        # H-028 FIX: propuesta de reserva vigente (null si no hay)
        'propuesta_reserva': _propuesta_reserva('whatsapp', phone),
    })


def _sugerencia_agente(phone, request):
    """Genera (lazy) o recupera el borrador del agente IA. Nunca rompe la vista.

    Opt-in: solo se genera si el caller pide `?sugerencia=1`. Así prender el
    agente no dispara gasto de LLM en cada apertura de chat de la bandeja actual
    hasta que aremko-cli conecte el parámetro explícitamente.
    """
    if not _truthy(request.GET.get('sugerencia', '0')):
        return None
    try:
        from whatsapp_agent.agent import generar_sugerencia, sugerencia_to_dict
        return sugerencia_to_dict(generar_sugerencia(phone))
    except Exception:  # noqa: BLE001 — el agente es opcional; jamás tumbar la conversación
        import logging
        logging.getLogger(__name__).exception('Agente WA: fallo generando sugerencia para %s', phone)
        return None


def _es_inicio_turno(texto):
    """True si el texto del staff es un saludo de inicio de turno (determinístico)."""
    import unicodedata
    t = unicodedata.normalize('NFKD', (texto or '').lower()).encode('ascii', 'ignore').decode().strip()
    if not t:
        return False
    triggers = (
        'empezando el dia', 'empezando mi dia', 'empezando la jornada', 'empezando el turno',
        'buenos dias', 'buenas tardes', 'buenas noches', 'buen dia',
        'inicio turno', 'inicio de turno', 'inicio mi turno', 'iniciando turno', 'inicio jornada',
        'comienzo turno', 'comenzando turno', 'empiezo turno', 'empezar turno',
        'comenzando el dia', 'comienzo el dia', 'partiendo el dia', 'partiendo la jornada',
        'llegue', 'ya llegue', 'aca estoy', 'presente',
    )
    return any(trig in t for trig in triggers)


def _briefing_staff(phone, recientes):
    """Luna Interna (H-037): si `phone` es staff whitelisted con responde_auto y el
    ÚLTIMO mensaje del hilo es un entrante de inicio de turno SIN responder, devuelve
    el briefing del día con el formato de `sugerencia_agente`. Si no, None.

    Idempotencia: solo dispara cuando el último mensaje es entrante; una vez que
    aremko-cli envía y postea el saliente, el último pasa a 'out' → no se re-dispara.
    """
    try:
        from personal_operativo.services import buscar_personal, construir_briefing
        persona = buscar_personal(phone)
        if not persona or not persona.responde_auto or not recientes:
            return None
        ultimo = recientes[-1]
        if ultimo.direction != 'in' or not _es_inicio_turno(ultimo.body or ''):
            return None
        from django.utils import timezone
        return {
            'texto': construir_briefing(persona),
            'escalar': False,
            'motivo': None,
            'modo': 'interno',
            'modelo': 'briefing',
            'error': None,
            'generada_at': timezone.now().isoformat(),
            'responde_a': ultimo.wa_message_id,
        }
    except Exception:  # noqa: BLE001 — jamás tumbar la conversación
        import logging
        logging.getLogger(__name__).exception('Briefing staff falló para %s', phone)
        return None


def _truthy(value):
    return str(value or '').strip().lower() in ('1', 'true', 'yes', 'si', 'sí', 'on')


def conversations(request):
    """GET /api/whatsapp/conversations/ — una fila por conversación (teléfono),
    ordenadas por el mensaje más reciente primero.

    Query params:
      - solo_pendientes (bool, default false): solo las que esperan respuesta nuestra
        (hay un entrante más nuevo que el último saliente, o algún requiere_atencion).
      - limit (int, default 50, máx 200).

    Nota de diseño: el flag `requiere_atencion` vive en WhatsAppMessage (no en
    ContactoWhatsApp). Acá `requiere_atencion` = hay algún entrante sin atender.
    """
    err = _check_luna_key(request)
    if err:
        return err

    from django.db.models import Max, Count, Q

    solo_pendientes = _truthy(request.GET.get('solo_pendientes'))
    try:
        limit = min(max(int(request.GET.get('limit', 50)), 1), 200)
    except (ValueError, TypeError):
        limit = 50

    # Agregado por teléfono (llave natural de la conversación en WhatsApp).
    agg = list(
        WhatsAppMessage.objects.values('phone').annotate(
            ultimo_ts=Max('timestamp'),
            total=Count('id'),
            last_in=Max('timestamp', filter=Q(direction='in')),
            last_out=Max('timestamp', filter=Q(direction='out')),
            req=Count('id', filter=Q(direction='in', requiere_atencion=True)),
        ).order_by('-ultimo_ts')
    )

    # H-006: pendientes (req>0) PRIMERO, luego por recencia — antes del corte
    # [:limit]. Así un blast de plantillas salientes no empuja hacia abajo (ni
    # tira fuera del límite) una conversación con un entrante sin responder.
    _min_ts = datetime.min.replace(tzinfo=dt_tz.utc)  # guarda por si ultimo_ts es None
    agg.sort(key=lambda a: (a['req'] > 0, a['ultimo_ts'] or _min_ts), reverse=True)

    def _pendiente(a):
        # El pendiente se basa SOLO en requiere_atencion (lo limpian tanto
        # responder como marcar-atendido), no en el timestamp del último
        # mensaje: así "marcar como leído" saca la conversación aunque el
        # último mensaje sea entrante. (H-005)
        return a['req'] > 0

    if solo_pendientes:
        agg = [a for a in agg if _pendiente(a)]

    page = agg[:limit]
    phones = [a['phone'] for a in page]

    # Una sola pasada por los mensajes de los teléfonos de esta página:
    # último mensaje y cliente (primer no-nulo). El badge "sin responder" usa
    # el flag requiere_atencion (campo `req` del agregado), no el timestamp.
    last_msg = {}
    cliente_map = {}
    if phones:
        for m in (
            WhatsAppMessage.objects
            .filter(phone__in=phones)
            .select_related('cliente')
            .order_by('phone', '-timestamp')
        ):
            if m.phone not in last_msg:
                last_msg[m.phone] = m
            if m.phone not in cliente_map and m.cliente_id:
                cliente_map[m.phone] = m.cliente

    conversations_out = []
    for a in page:
        phone = a['phone']
        m = last_msg.get(phone)
        cli = cliente_map.get(phone)
        # Preview: caption si hay; si es adjunto sin texto, etiqueta (📷/🎥/📄...).
        if m and m.body:
            preview = m.body
        elif m and m.media_file:
            preview = _media_label(m.msg_type, m.original_filename)
        else:
            preview = ''
        conversations_out.append({
            'phone': phone,
            'cliente_id': cli.id if cli else None,
            'cliente_nombre': (cli.nombre if cli and cli.nombre else None),
            'ultimo_mensaje': preview,
            'ultimo_direction': (m.direction if m else None),
            'ultimo_timestamp': a['ultimo_ts'].isoformat() if a['ultimo_ts'] else None,
            'sin_responder': a['req'],
            'requiere_atencion': a['req'] > 0,
            'total_mensajes': a['total'],
        })

    return JsonResponse({
        'count': len(conversations_out),
        'conversations': conversations_out,
    })


@csrf_exempt
def marcar_atendido(request, phone):
    """POST /api/whatsapp/conversations/<phone>/marcar-atendido/ — saca la
    conversación de la cola de pendientes (limpia requiere_atencion de los
    entrantes de ese teléfono). Útil cuando se respondió por fuera de la Cloud API.
    """
    err = _check_luna_key(request)
    if err:
        return err
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    phone = (phone or '').strip()
    if not phone:
        return JsonResponse({'error': 'phone requerido'}, status=400)

    actualizado = WhatsAppMessage.objects.filter(
        phone=phone[:20], direction='in', requiere_atencion=True,
    ).update(requiere_atencion=False)

    return JsonResponse({
        'success': True,
        'phone': phone,
        'actualizado': bool(actualizado),
        'mensajes_actualizados': actualizado,
    })


@csrf_exempt
def editar_nombre(request, phone):
    """POST /api/whatsapp/conversations/<phone>/editar-nombre/ — corrige el
    Cliente.nombre desde la bandeja (los auto-creados traen el nombre de perfil
    de WhatsApp o 'WhatsApp <tel>', que a menudo no es el real). Body: {nombre}.
    Auditado en MovimientoCliente. Mismo guard luna-key que el resto de /whatsapp/.
    """
    err = _check_luna_key(request)
    if err:
        return err
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    phone = (phone or '').strip()
    if not phone:
        return JsonResponse({'ok': False, 'error': 'phone requerido'}, status=400)

    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        data = {}
    nombre = (data.get('nombre') or '').strip()
    if not nombre:
        return JsonResponse({'ok': False, 'error': 'nombre requerido'}, status=400)
    nombre = nombre[:100]

    cliente = _match_or_create_cliente(phone)
    if cliente is None:
        return JsonResponse({'ok': False, 'error': 'No se pudo resolver el cliente por teléfono'}, status=404)

    anterior = cliente.nombre or ''
    if nombre != anterior:
        cliente.nombre = nombre
        cliente.save(update_fields=['nombre'])
        try:
            from ..models import MovimientoCliente
            MovimientoCliente.objects.create(
                cliente=cliente,
                tipo_movimiento='edicion_nombre',
                comentarios=f"Nombre corregido desde la bandeja WhatsApp: '{anterior}' → '{nombre}'",
            )
        except Exception:
            pass  # la auditoría no debe bloquear la corrección

    return JsonResponse({
        'ok': True,
        'cliente_id': cliente.id,
        'cliente_nombre': cliente.nombre,
    })


# ============================================================================
# Agente IA WhatsApp (H-007) — config singleton editable desde aremko-cli.
# ============================================================================

@csrf_exempt
def agente_config(request):
    """GET/POST /api/whatsapp/agente/config — lee o actualiza la config del agente.

    GET  → {activo, modo, persona_tono, link_reserva, model_name, modelo_efectivo,
            temperature, max_tokens, history_window, pausa_horas_tras_humano, prompt_version}
    POST → actualiza los campos enviados (subconjunto permitido). luna-key.
    """
    err = _check_luna_key(request)
    if err:
        return err

    from whatsapp_agent.agent import config_to_dict, get_config
    config = get_config()

    if request.method == 'GET':
        return JsonResponse({'ok': True, 'config': config_to_dict(config)})

    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    cambios = []
    # Campos de texto / selección.
    if 'activo' in data:
        config.activo = _truthy(data.get('activo'))
        cambios.append('activo')
    if 'modo' in data:
        modo = (data.get('modo') or '').strip()
        validos = {c[0] for c in config.MODO_CHOICES}
        if modo not in validos:
            return JsonResponse({'ok': False, 'error': f'modo inválido (use uno de {sorted(validos)})'}, status=400)
        config.modo = modo
        cambios.append('modo')
    if 'persona_tono' in data:
        config.persona_tono = (data.get('persona_tono') or '').strip()
        cambios.append('persona_tono')
    if 'conocimiento' in data:
        config.conocimiento = (data.get('conocimiento') or '').strip()
        cambios.append('conocimiento')
    if 'link_reserva' in data:
        config.link_reserva = (data.get('link_reserva') or '').strip()[:300]
        cambios.append('link_reserva')
    if 'model_name' in data:
        config.model_name = (data.get('model_name') or '').strip()[:120]
        cambios.append('model_name')
    # Mensaje de ausencia (H-008).
    if 'ausencia_activa' in data:
        config.ausencia_activa = _truthy(data.get('ausencia_activa'))
        cambios.append('ausencia_activa')
    if 'ausencia_mensaje' in data:
        config.ausencia_mensaje = (data.get('ausencia_mensaje') or '').strip()
        cambios.append('ausencia_mensaje')
    # Campos numéricos (validación suave; ignora valores no parseables).
    for campo, lo, hi in (('temperature', 0.0, 2.0), ('max_tokens', 1, 4000),
                          ('history_window', 0, 50), ('pausa_horas_tras_humano', 0, 168),
                          ('ausencia_anti_spam_horas', 0, 168)):
        if campo in data:
            try:
                val = float(data.get(campo)) if campo == 'temperature' else int(data.get(campo))
            except (TypeError, ValueError):
                return JsonResponse({'ok': False, 'error': f'{campo} inválido'}, status=400)
            if not (lo <= val <= hi):
                return JsonResponse({'ok': False, 'error': f'{campo} fuera de rango [{lo}, {hi}]'}, status=400)
            setattr(config, campo, val)
            cambios.append(campo)

    if cambios:
        config.save()

    return JsonResponse({'ok': True, 'actualizado': cambios, 'config': config_to_dict(config)})


@csrf_exempt
def agente_feedback(request):
    """POST /api/whatsapp/agente/feedback — captura el delta borrador-vs-enviado (H-010 parte 1).

    Body: {phone, wa_message_id, borrador, enviado, editado:bool} → {ok}. Lo reporta
    aremko-cli tras un envío que tenía borrador. Fire-and-forget: nunca debe romper
    el flujo de aremko-cli, así que ante cualquier problema responde igual.
    """
    err = _check_luna_key(request)
    if err:
        return err
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    try:
        from whatsapp_agent.models import AgenteFeedback
        borrador = data.get('borrador') or ''
        enviado = data.get('enviado') or ''
        if 'editado' in data:
            editado = _truthy(data.get('editado'))
        else:
            editado = borrador.strip() != enviado.strip()
        fb = AgenteFeedback.objects.create(
            phone=(data.get('phone') or '')[:20],
            wa_message_id=(data.get('wa_message_id') or '')[:128],
            borrador=borrador,
            enviado=enviado,
            editado=editado,
        )
        return JsonResponse({'ok': True, 'feedback_id': fb.id, 'editado': editado})
    except Exception:  # noqa: BLE001 — fire-and-forget: no romper el envío de aremko-cli
        import logging
        logging.getLogger(__name__).exception('Agente feedback: no se pudo guardar')
        return JsonResponse({'ok': False}, status=200)


@csrf_exempt
def agente_procesar_aprendizaje(request):
    """POST /api/whatsapp/agente/procesar-aprendizaje — clasifica el feedback editado (H-013).

    Procesa un lote acotado (~50) de `AgenteFeedback` editados sin procesar y crea las
    `SugerenciaAprendizaje` accionables. Idempotente; pensado para un botón manual. Si
    queda backlog, se vuelve a llamar. Devuelve conteos.
    """
    err = _check_luna_key(request)
    if err:
        return err
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        from whatsapp_agent.aprendizaje import procesar_pendientes
        try:
            data = json.loads(request.body or b'{}')
        except (ValueError, UnicodeDecodeError):
            data = {}
        limite = data.get('limite') or 50
        res = procesar_pendientes(limite)
        return JsonResponse({
            'ok': True,
            'procesados': res['procesados'],
            'creadas': res['creadas'],
            'errores': res['errores'],
            'resumen': res['detalle'],
        })
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).exception('Agente: error procesando aprendizaje')
        return JsonResponse({'ok': False, 'error': 'error procesando aprendizaje'}, status=500)


def _sugerencia_aprendizaje_dict(s):
    return {
        'id': s.id, 'phone': s.phone, 'tipo': s.tipo, 'estado': s.estado,
        'texto_propuesto': s.texto_propuesto, 'ref_catalogo': s.ref_catalogo,
        'motivo': s.motivo, 'borrador': s.borrador, 'enviado': s.enviado,
        'destino': ('Conocimiento del agente' if s.tipo == 'regla'
                    else 'Catálogo (aplica Jorge a mano)' if s.tipo == 'hecho_catalogo'
                    else '—'),
        'aprueba': 'Jorge' if s.tipo == 'hecho_catalogo' else 'Deborah/Jorge',
        'created_at': s.created_at.isoformat(),
    }


@csrf_exempt
def agente_sugerencias_aprendizaje(request):
    """GET /api/whatsapp/agente/sugerencias-aprendizaje — pendientes (H-010 p2). luna-key."""
    err = _check_luna_key(request)
    if err:
        return err
    from whatsapp_agent.models import SugerenciaAprendizaje
    estado = (request.GET.get('estado') or 'pendiente').strip()
    qs = SugerenciaAprendizaje.objects.all()
    if estado != 'todas':
        qs = qs.filter(estado=estado)
    try:
        limite = min(max(int(request.GET.get('limit', 100)), 1), 500)
    except (ValueError, TypeError):
        limite = 100
    items = [_sugerencia_aprendizaje_dict(s) for s in qs[:limite]]
    return JsonResponse({'ok': True, 'sugerencias': items, 'count': len(items)})


@csrf_exempt
def agente_sugerencia_aprobar(request, sug_id):
    """POST /api/whatsapp/agente/sugerencias-aprendizaje/<id>/aprobar — aplica según tipo.

    Body opcional {texto} para editar el texto antes de aprobar. `regla` se agrega al
    Conocimiento; `hecho_catalogo` queda marcada para que Jorge aplique el cambio a mano
    en el admin (MVP: no auto-edita el catálogo por el drift AR-034).
    """
    err = _check_luna_key(request)
    if err:
        return err
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    from django.utils import timezone
    from whatsapp_agent.agent import get_config
    from whatsapp_agent.models import SugerenciaAprendizaje

    sug = SugerenciaAprendizaje.objects.filter(id=sug_id).first()
    if not sug:
        return JsonResponse({'ok': False, 'error': 'no encontrada'}, status=404)
    if sug.estado != 'pendiente':
        return JsonResponse({'ok': False, 'error': f'ya está {sug.estado}'}, status=409)

    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        data = {}
    texto = (data.get('texto') or sug.texto_propuesto or '').strip()

    if sug.tipo == 'regla' and texto:
        config = get_config()
        actual = (config.conocimiento or '').strip()
        config.conocimiento = (actual + '\n' + texto).strip() if actual else texto
        config.save(update_fields=['conocimiento'])
        sug.aplicado_info = 'Agregada al Conocimiento del agente'
    elif sug.tipo == 'hecho_catalogo':
        sug.aplicado_info = f'Marcada para aplicar en el catálogo: {sug.ref_catalogo or texto}'.strip()
    else:
        sug.aplicado_info = 'Aprobada'

    sug.texto_propuesto = texto
    sug.estado = 'aprobada'
    sug.resuelto_at = timezone.now()
    sug.save(update_fields=['texto_propuesto', 'estado', 'aplicado_info', 'resuelto_at'])
    return JsonResponse({'ok': True, 'estado': sug.estado, 'aplicado': sug.aplicado_info})


@csrf_exempt
def agente_sugerencia_descartar(request, sug_id):
    """POST /api/whatsapp/agente/sugerencias-aprendizaje/<id>/descartar. luna-key."""
    err = _check_luna_key(request)
    if err:
        return err
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    from django.utils import timezone
    from whatsapp_agent.models import SugerenciaAprendizaje
    sug = SugerenciaAprendizaje.objects.filter(id=sug_id).first()
    if not sug:
        return JsonResponse({'ok': False, 'error': 'no encontrada'}, status=404)
    if sug.estado != 'pendiente':
        return JsonResponse({'ok': False, 'error': f'ya está {sug.estado}'}, status=409)
    sug.estado = 'descartada'
    sug.resuelto_at = timezone.now()
    sug.save(update_fields=['estado', 'resuelto_at'])
    return JsonResponse({'ok': True, 'estado': sug.estado})


# ============================================================================
# Campaña de plantillas Meta (Operación Vuelta a Casa) — Django decide, Go envía.
# Django arma la bandeja (ContactoWhatsApp salva 1) y resuelve los params; Go
# hace el SendTemplate y reporta con mark-template-sent / mark-template-failed.
# ============================================================================

def _resolver_params(contacto, hoy):
    """Resuelve la lista ordenada de params {{1}},{{2}}… para la plantilla Meta,
    según script.meta_variables_orden, usando el mismo render context del cron."""
    from ..services.bandeja_whatsapp_service import build_render_context
    orden = contacto.script.meta_variables_orden or []
    if not orden:
        return []
    cliente = contacto.cliente
    try:
        tax = cliente.taxonomia
    except Exception:
        tax = None
    ctx = build_render_context(cliente, tax, hoy)
    # SafeDict: claves faltantes → ''. Convertir todo a str (Meta exige strings).
    return [str(ctx.get(ph, '') or '') for ph in orden]


def pending_template_sends(request):
    """GET /api/whatsapp/pending-template-sends?limit=N — contactos APROBADOS
    listos para envío por plantilla Meta (H-012: gate de aprobación).

    Elegible = estado='aprobado' (Deborah aprobó) y el script tiene meta_template_name.
    Orden: prioridad ASC (más urgente primero), luego fecha_sugerido ASC.
    """
    err = _check_luna_key(request)
    if err:
        return err

    try:
        limit = min(max(int(request.GET.get('limit', 50)), 1), 200)
    except (ValueError, TypeError):
        limit = 50

    hoy = timezone.now().date()

    qs = (
        ContactoWhatsApp.objects
        .filter(estado='aprobado')
        .exclude(script__meta_template_name='')
        .exclude(script__meta_template_name__isnull=True)
        .select_related('cliente', 'script')
        .order_by('prioridad', 'fecha_sugerido', 'id')[:limit]
    )

    items = []
    for c in qs:
        phone = (c.cliente.telefono or '').strip() if c.cliente else ''
        if not phone:
            continue  # sin teléfono no se puede enviar; el cron normal no debería generarlo
        items.append({
            'contacto_id': c.id,
            'phone': phone,
            'meta_template_name': c.script.meta_template_name,
            'language': c.script.meta_language or 'es',
            'params': _resolver_params(c, hoy),
            'script_id': c.script.script_id,
        })

    return JsonResponse({'count': len(items), 'pending': items})


# ============================================================================
# H-012 — Bandeja de envíos por plantilla: aprobación antes de enviar.
# El cron diario deja ContactoWhatsApp en estado='pendiente' (= por aprobar).
# Deborah aprueba → estado='aprobado' → pending-template-sends los envía por Cloud API.
# ============================================================================

def _envio_por_aprobar_dict(c):
    cli = c.cliente
    return {
        'contacto_id': c.id,
        'cliente_id': cli.id if cli else None,
        'cliente_nombre': (cli.nombre if cli else '') or '',
        'phone': ((cli.telefono or '').strip() if cli else ''),
        'motivo': c.eje_valor_snapshot or (c.script.estado_valor_target if c.script_id else ''),
        'script_id': c.script.script_id if c.script_id else '',
        'plantilla': c.script.meta_template_name if c.script_id else '',
        'preview': c.mensaje_renderizado or '',
        'salva': c.salva,
        'prioridad': c.prioridad,
        'fecha_sugerido': c.fecha_sugerido.isoformat() if c.fecha_sugerido else None,
    }


def bandeja_envios_por_aprobar(request):
    """GET /api/whatsapp/bandeja-envios?estado=por_aprobar — envíos de plantilla a aprobar.

    Lista los `ContactoWhatsApp` pendientes cuyo script tiene plantilla Meta (los que
    SÍ se pueden enviar). Agrupa por motivo en el cliente; acá van planos con su motivo.
    """
    err = _check_luna_key(request)
    if err:
        return err
    try:
        limit = min(max(int(request.GET.get('limit', 200)), 1), 500)
    except (ValueError, TypeError):
        limit = 200
    qs = (
        ContactoWhatsApp.objects
        .filter(estado='pendiente')
        .exclude(script__meta_template_name='')
        .exclude(script__meta_template_name__isnull=True)
        .select_related('cliente', 'script')
        .order_by('prioridad', 'fecha_sugerido', 'id')[:limit]
    )
    items = [_envio_por_aprobar_dict(c) for c in qs if c.cliente and (c.cliente.telefono or '').strip()]
    return JsonResponse({'ok': True, 'count': len(items), 'envios': items})


@csrf_exempt
def bandeja_envio_aprobar(request, contacto_id):
    """POST /api/whatsapp/bandeja-envios/<id>/aprobar — marca un envío como aprobado."""
    err = _check_luna_key(request)
    if err:
        return err
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    c = ContactoWhatsApp.objects.filter(id=contacto_id).select_related('script').first()
    if not c:
        return JsonResponse({'ok': False, 'error': 'no encontrado'}, status=404)
    if c.estado != 'pendiente':
        return JsonResponse({'ok': False, 'error': f'estado actual: {c.estado}'}, status=409)
    if not (c.script_id and c.script.meta_template_name):
        return JsonResponse({'ok': False, 'error': 'el script no tiene plantilla Meta asignada'}, status=400)
    c.estado = 'aprobado'
    c.save(update_fields=['estado'])
    return JsonResponse({'ok': True, 'contacto_id': c.id, 'estado': c.estado})


@csrf_exempt
def bandeja_envio_descartar(request, contacto_id):
    """POST /api/whatsapp/bandeja-envios/<id>/descartar — no enviar este envío."""
    err = _check_luna_key(request)
    if err:
        return err
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    c = ContactoWhatsApp.objects.filter(id=contacto_id).first()
    if not c:
        return JsonResponse({'ok': False, 'error': 'no encontrado'}, status=404)
    if c.estado != 'pendiente':
        return JsonResponse({'ok': False, 'error': f'estado actual: {c.estado}'}, status=409)
    c.estado = 'descartado'
    c.save(update_fields=['estado'])
    return JsonResponse({'ok': True, 'contacto_id': c.id, 'estado': c.estado})


@csrf_exempt
def bandeja_envios_aprobar_lote(request):
    """POST /api/whatsapp/bandeja-envios/aprobar-lote — aprueba un lote.

    Body: {ids:[...]}  o  {motivo:"<eje_valor>"} (aprueba todos los pendientes de ese
    motivo con plantilla). Devuelve cuántos se aprobaron.
    """
    err = _check_luna_key(request)
    if err:
        return err
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    qs = (ContactoWhatsApp.objects.filter(estado='pendiente')
          .exclude(script__meta_template_name='')
          .exclude(script__meta_template_name__isnull=True))
    ids = data.get('ids')
    motivo = (data.get('motivo') or '').strip()
    if ids:
        qs = qs.filter(id__in=ids)
    elif motivo:
        qs = qs.filter(eje_valor_snapshot=motivo)
    else:
        return JsonResponse({'ok': False, 'error': 'indica ids[] o motivo'}, status=400)

    aprobados = qs.update(estado='aprobado')
    return JsonResponse({'ok': True, 'aprobados': aprobados})


@csrf_exempt
def mark_template_sent(request):
    """POST /api/whatsapp/mark-template-sent — Go confirma envío de la plantilla.

    Body JSON: { "contacto_id": 123, "wa_message_id": "wamid..." }
    Marca el ContactoWhatsApp como enviado (operador='cloud-api') y registra el
    WhatsAppMessage saliente. Idempotente por contacto_id.
    """
    err = _check_luna_key(request)
    if err:
        return err
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, TypeError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    contacto_id = data.get('contacto_id')
    wa_id = (data.get('wa_message_id') or '').strip()
    if not contacto_id:
        return JsonResponse({'error': 'contacto_id es obligatorio'}, status=400)

    contacto = (
        ContactoWhatsApp.objects.select_related('cliente').filter(id=contacto_id).first()
    )
    if not contacto:
        return JsonResponse({'error': 'contacto no encontrado'}, status=404)

    # Idempotencia por contacto_id: si ya está enviado, no duplicar.
    if contacto.estado == 'enviado':
        return JsonResponse({
            'success': True, 'idempotent': True,
            'contacto_id': contacto.id, 'estado': contacto.estado,
        })

    now = timezone.now()
    contacto.estado = 'enviado'
    contacto.fecha_envio = now
    contacto.operador = 'cloud-api'
    contacto.save(update_fields=['estado', 'fecha_envio', 'operador'])

    cliente = contacto.cliente
    phone = (cliente.telefono or '').strip() if cliente else ''

    # Registrar el saliente en el hilo (idempotente por wa_message_id).
    message_id = None
    if wa_id:
        existing = WhatsAppMessage.objects.filter(wa_message_id=wa_id).first()
        if existing:
            message_id = existing.id
        else:
            msg = WhatsAppMessage.objects.create(
                cliente=cliente, direction='out', wa_message_id=wa_id,
                phone=phone[:20], body=contacto.mensaje_renderizado or '',
                msg_type='template', timestamp=now, status='sent',
            )
            message_id = msg.id

    if phone:
        _outbound_side_effects(cliente, phone, now)

    return JsonResponse({
        'success': True,
        'contacto_id': contacto.id,
        'estado': contacto.estado,
        'message_id': message_id,
    })


@csrf_exempt
def mark_template_failed(request):
    """POST /api/whatsapp/mark-template-failed — Go reporta fallo de envío.

    Body JSON: { "contacto_id": 123, "error": "..." }
    Saca el contacto de 'pendiente' (→ 'omitido') para que no quede colgado;
    como 'omitido' no cuenta salva ni satura, el cron del día siguiente puede
    re-generarlo como salva 1 (reintento natural). Guarda el error en nota.
    Idempotente: si ya no está pendiente, responde ok sin cambios.
    """
    err = _check_luna_key(request)
    if err:
        return err
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, TypeError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    contacto_id = data.get('contacto_id')
    error_txt = (data.get('error') or '').strip()
    if not contacto_id:
        return JsonResponse({'error': 'contacto_id es obligatorio'}, status=400)

    contacto = ContactoWhatsApp.objects.filter(id=contacto_id).first()
    if not contacto:
        return JsonResponse({'error': 'contacto no encontrado'}, status=404)

    if contacto.estado != 'pendiente':
        return JsonResponse({
            'success': True, 'idempotent': True,
            'contacto_id': contacto.id, 'estado': contacto.estado,
        })

    nota = contacto.nota_operador or ''
    marca = f"[cloud-api fallo {timezone.now():%Y-%m-%d %H:%M}] {error_txt}".strip()
    contacto.nota_operador = (nota + ('\n' if nota else '') + marca)[:5000]
    contacto.estado = 'omitido'
    contacto.operador = 'cloud-api'
    contacto.save(update_fields=['estado', 'operador', 'nota_operador'])

    return JsonResponse({
        'success': True,
        'contacto_id': contacto.id,
        'estado': contacto.estado,
    })
