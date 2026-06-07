"""Conexión-Masajes — Bandeja de salida (consumida por aremko-cli / Go).

Los emails de seguimiento NO se envían solos: quedan en estado 'pendiente' y se
revisan/editan/envían manualmente desde la bandeja de salida de aremko-cli
(Debora / Angélica / Jorge).

Auth: header X-API-Key (LUNA_API_KEY), mismo esquema que los endpoints WhatsApp.

Rutas:
  GET  /api/masaje/outbox/                 → lista (para_enviar[] + programados[])
  GET  /api/masaje/outbox/<id>/preview/    → HTML final (vista previa, text/html)
  PATCH/POST /api/masaje/outbox/<id>/      → editar asunto/cuerpo (+ operador)
  POST /api/masaje/outbox/<id>/send/       → enviar ahora (+ operador)
  POST /api/masaje/outbox/<id>/cancel/     → cancelar (+ operador)
"""

import json

from django.http import JsonResponse, HttpResponse, Http404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..models import SeguimientoBienestarMasaje
from ..services import masaje_seguimiento_service as svc
from .whatsapp_api_views import _check_luna_key


def _body(request):
    """Parsea el body JSON (o form). Devuelve dict (vacío si no hay/!válido)."""
    if request.body:
        try:
            return json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            pass
    return {k: v for k, v in request.POST.items()}


# Etiquetas legibles de region_geografica (mismas categorías que la bandeja WhatsApp).
REGION_LABELS = {
    'sur': 'Sur',
    'nacional': 'Resto de Chile',
    'extranjero': 'Extranjero',
    'sin_clasificar': 'Sin clasificar',
}


def _cliente_de(seg):
    p = seg.participante if seg.participante_id else None
    return (p.cliente if p else None) or (seg.cliente if seg.cliente_id else None)


def _destinatario(seg):
    """(nombre, email) del destinatario, desde participante o cliente."""
    p = seg.participante if seg.participante_id else None
    cliente = _cliente_de(seg)
    nombre = ((p.nombre if p else '') or (cliente.nombre if cliente else '') or '').strip()
    email = ((p.email if p else '') or (cliente.email if cliente else '') or '').strip()
    return nombre, email


def _contexto_reserva(seg):
    """(servicio, fecha_visita) de la línea de masaje del participante.
    Usa el mismo emparejamiento participante↔línea que la agenda; si no hay
    participante, cae a la primera línea de masaje de la reserva."""
    p = seg.participante if seg.participante_id else None
    reserva = (p.reserva if p else None) or (seg.reserva if seg.reserva_id else None)
    if reserva is None:
        return None, None
    linea = None
    if p is not None:
        try:
            from ..services.masaje_participantes_service import mapear_participante_a_linea
            linea = mapear_participante_a_linea(reserva).get(p.id)
        except Exception:
            linea = None
    if linea is None:
        linea = (reserva.reservaservicios
                 .filter(servicio__tipo_servicio='masaje')
                 .select_related('servicio').order_by('id').first())
    if linea is None:
        return None, None
    servicio = linea.servicio.nombre if linea.servicio_id else None
    fecha_visita = linea.fecha_agendamiento.isoformat() if linea.fecha_agendamiento else None
    return servicio, fecha_visita


def _serialize(seg, include_preview=False):
    p = seg.participante if seg.participante_id else None
    cliente = _cliente_de(seg)
    nombre, email = _destinatario(seg)

    # Geo (mismas fuentes que la bandeja WhatsApp)
    ciudad = (cliente.ciudad_normalizada.nombre_canonico
              if (cliente and cliente.ciudad_normalizada_id) else None)
    region = (cliente.region_geografica if cliente else 'sin_clasificar') or 'sin_clasificar'

    # Teléfono (Cliente.telefono ya viene normalizado E.164; participante como respaldo)
    telefono = ((cliente.telefono if cliente else '') or (p.telefono if p else '') or '').strip()

    # Contexto de la reserva
    servicio, fecha_visita = _contexto_reserva(seg)
    num_visitas = cliente.numero_visitas() if cliente else 0

    data = {
        'id': seg.id,
        'tipo_email': seg.tipo_email,
        'tipo_label': seg.get_tipo_email_display(),
        'estado': seg.estado,
        'destinatario_nombre': nombre,
        'destinatario_email': email,
        'destinatario_telefono': telefono,
        'ciudad': ciudad,
        'region': region,
        'region_label': REGION_LABELS.get(region, region),
        'apto_visita': region == 'sur',
        'servicio': servicio,
        'fecha_visita': fecha_visita,
        'num_visitas': num_visitas,
        'cliente_nuevo': num_visitas <= 1,
        'fecha_programada': seg.fecha_programada.isoformat() if seg.fecha_programada else None,
        'fecha_envio': seg.fecha_envio.isoformat() if seg.fecha_envio else None,
        'asunto': seg.asunto,
        'cuerpo': seg.cuerpo,
        'reserva_id': seg.reserva_id,
        'enviado_por': seg.enviado_por,
        'editado_por': seg.editado_por,
        'editado_at': seg.editado_at.isoformat() if seg.editado_at else None,
        'error_log': seg.error_log,
    }
    if include_preview:
        data['preview_html'] = svc.construir_html_preview(seg)
    return data


def _get_seg(seg_id):
    seg = SeguimientoBienestarMasaje.objects.filter(id=seg_id).select_related(
        'participante', 'participante__cliente', 'participante__cliente__ciudad_normalizada',
        'cliente', 'cliente__ciudad_normalizada').first()
    if seg is None:
        raise Http404("Seguimiento no encontrado")
    return seg


@csrf_exempt
@require_http_methods(["GET"])
def outbox_list(request):
    """Lista los seguimientos pendientes. Dos grupos:
    - para_enviar: vencidos (fecha_programada <= ahora), listos para revisar/enviar.
    - programados: futuros (fecha_programada > ahora).
    Query: ?incluir_programados=0 para omitir los futuros; ?limit=N (default 200)."""
    err = _check_luna_key(request)
    if err:
        return err

    try:
        limit = min(int(request.GET.get('limit', 200)), 500)
    except (ValueError, TypeError):
        limit = 200
    incluir_prog = request.GET.get('incluir_programados', '1') not in ('0', 'false', 'no')

    ahora = timezone.now()
    base = SeguimientoBienestarMasaje.objects.filter(estado='pendiente').select_related(
        'participante', 'participante__cliente', 'participante__cliente__ciudad_normalizada',
        'cliente', 'cliente__ciudad_normalizada')

    venc = base.filter(fecha_programada__lte=ahora).order_by('fecha_programada')[:limit]
    para_enviar = [_serialize(s, include_preview=True) for s in venc]

    programados = []
    if incluir_prog:
        fut = base.filter(fecha_programada__gt=ahora).order_by('fecha_programada')[:limit]
        programados = [_serialize(s) for s in fut]

    return JsonResponse({
        'ok': True,
        'para_enviar': para_enviar,
        'programados': programados,
        'total_para_enviar': len(para_enviar),
        'total_programados': len(programados),
    })


@require_http_methods(["GET"])
def outbox_preview(request, seg_id):
    """HTML final del email (para iframe en la bandeja)."""
    err = _check_luna_key(request)
    if err:
        return err
    seg = _get_seg(seg_id)
    return HttpResponse(svc.construir_html_preview(seg), content_type='text/html; charset=utf-8')


@csrf_exempt
@require_http_methods(["PATCH", "POST"])
def outbox_edit(request, seg_id):
    """Edita asunto y/o cuerpo de un seguimiento pendiente. Body: {asunto, cuerpo,
    operador}. Registra editado_por/editado_at."""
    err = _check_luna_key(request)
    if err:
        return err
    seg = _get_seg(seg_id)
    if seg.estado != 'pendiente':
        return JsonResponse({'ok': False, 'error': f"No se puede editar un seguimiento en estado '{seg.estado}'."}, status=409)

    data = _body(request)
    operador = (data.get('operador') or '').strip()
    fields = []
    if 'asunto' in data:
        seg.asunto = (data.get('asunto') or '')[:255]
        fields.append('asunto')
    if 'cuerpo' in data:
        seg.cuerpo = data.get('cuerpo') or ''
        fields.append('cuerpo')
    if not fields:
        return JsonResponse({'ok': False, 'error': 'Nada que editar (envía asunto y/o cuerpo).'}, status=400)

    seg.editado_por = operador[:80]
    seg.editado_at = timezone.now()
    fields += ['editado_por', 'editado_at']
    seg.save(update_fields=fields)
    return JsonResponse({'ok': True, 'item': _serialize(seg, include_preview=True)})


@csrf_exempt
@require_http_methods(["POST"])
def outbox_send(request, seg_id):
    """Envía ahora un seguimiento pendiente. Body: {operador}."""
    err = _check_luna_key(request)
    if err:
        return err
    seg = _get_seg(seg_id)
    if seg.estado != 'pendiente':
        return JsonResponse({'ok': False, 'error': f"El seguimiento ya está en estado '{seg.estado}'."}, status=409)

    data = _body(request)
    operador = (data.get('operador') or '').strip()
    enviado = svc.enviar_seguimiento(seg, operador=operador)
    seg.refresh_from_db()
    return JsonResponse({
        'ok': bool(enviado),
        'estado': seg.estado,
        'error': seg.error_log or None,
        'item': _serialize(seg),
    }, status=200 if enviado else 422)


@csrf_exempt
@require_http_methods(["POST"])
def outbox_cancel(request, seg_id):
    """Cancela un seguimiento pendiente. Body: {operador}."""
    err = _check_luna_key(request)
    if err:
        return err
    seg = _get_seg(seg_id)
    if seg.estado not in ('pendiente',):
        return JsonResponse({'ok': False, 'error': f"No se puede cancelar un seguimiento en estado '{seg.estado}'."}, status=409)

    data = _body(request)
    operador = (data.get('operador') or '').strip()
    seg.estado = 'cancelado'
    seg.editado_por = operador[:80]
    seg.editado_at = timezone.now()
    seg.error_log = (f"Cancelado por {operador}" if operador else "Cancelado")
    seg.save(update_fields=['estado', 'editado_por', 'editado_at', 'error_log'])
    return JsonResponse({'ok': True, 'item': _serialize(seg)})
