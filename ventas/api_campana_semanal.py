"""Correo semanal: Datamatic genera, Aremko envía (H-111).

    POST /marketing/api/campana-semanal/
    X-API-KEY: <AUTOMATION_API_KEY>        (la misma llave del catálogo y las reseñas)
    {"asunto": "...", "cuerpo_html": "<table>…</table>", "nombre": "?", "lotes": 1, "origen": "?"}

Lo que decidió Jorge (12-09-2026) y explica cada regla de abajo:

- **No se dispara sola.** La campaña nace en Borrador; alguien la revisa en el
  admin y la pasa a «Lista para envío». Recién ahí el cron la manda.
- **Máximo 1.000 por lote.** Un correo a mil personas con un error no se
  deshace; el tope lo pone el sistema, no la buena intención.
- **El lote lo arma Aremko.** Van todos los clientes con correo, en fila:
  primero los que compraron hace menos, saltando a quien ya recibió un correo
  hace poco. Datamatic manda asunto y cuerpo; el segmento NO se acepta (si
  llega uno distinto de «todos», 400): una pantalla que dice «va a los de la
  zona» cuando el motor eligió otra cosa es una pantalla que miente.
- **La baja tiene que quedar clara.** No es cosa de este archivo: el pie lo
  agrega el motor al enviar (`enviar_campana_email`), por eso el cuerpo que
  llega acá NO debe traer pie propio.

Idempotente por `nombre`: la misma llamada dos veces devuelve las campañas que
ya existen (200, `repetida: true`) en vez de duplicar destinatarios.
"""
from __future__ import annotations

import datetime
import json
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import F, Max, Q
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import (Cliente, EmailBlacklist, EmailCampaign, EmailRecipient,
                     NewsletterSubscriber)

logger = logging.getLogger(__name__)

TOPE_LOTE = 1000            # Jorge, 12-09-2026: «máximo 1000 por cada lote»
MAX_LOTES = 6               # con 5.282 elegibles al 12-09 alcanza para toda la base
DIAS_SILENCIO = 28          # nadie recibe dos boletines en menos de 4 semanas
MAX_CUERPO_BYTES = 100 * 1024   # donde Gmail recorta y esconde el pie de baja
MAX_ASUNTO = 300
SEGMENTOS_ACEPTADOS = ('', 'todos', 'todos_con_email')
ESTADOS_ESPERANDO = ('draft', 'ready', 'sending')
BASE_PUBLICA = 'https://www.aremko.cl'
SCHEDULE = {'start_time': '08:00', 'end_time': '21:00', 'batch_size': 50,
            'interval_minutes': 5, 'ai_enabled': False}


def _api_key_ok(request) -> bool:
    esperada = getattr(settings, 'AUTOMATION_API_KEY', '') or ''
    return bool(esperada) and request.headers.get('X-API-KEY', '') == esperada


def _error(msg, status=400):
    return JsonResponse({'ok': False, 'error': msg}, status=status)


def _primer_nombre(nombre) -> str:
    partes = (nombre or '').strip().split()
    return partes[0] if partes else 'Cliente'


def _email_valido(email: str) -> bool:
    try:
        validate_email(email)
    except ValidationError:
        return False
    return True


def fila_de_elegibles():
    """Quién recibiría el próximo boletín, y en qué orden. La fila completa.

    1. Clientes con correo válido; un correo repetido entre varios clientes
       entra una sola vez (en minúsculas).
    2. Fuera: lista negra activa, bajas del newsletter, y correos que ya están
       esperando en otra campaña (borrador / lista / enviando).
    3. Fuera: quien recibió un correo de campaña en los últimos 28 días.
    4. Orden: última compra más reciente primero; sin compra al final.
    """
    ahora = timezone.now()
    bajas = {e.lower() for e in EmailBlacklist.objects.filter(is_active=True)
             .values_list('email', flat=True)}
    bajas |= {e.lower() for e in NewsletterSubscriber.objects.filter(is_active=False)
              .values_list('email', flat=True)}
    esperando = {e.lower() for e in EmailRecipient.objects
                 .filter(status='pending', send_enabled=True,
                         campaign__status__in=ESTADOS_ESPERANDO)
                 .values_list('email', flat=True)}
    recientes = {e.lower() for e in EmailRecipient.objects
                 .filter(sent_at__gte=ahora - datetime.timedelta(days=DIAS_SILENCIO))
                 .values_list('email', flat=True)}

    clientes = (Cliente.objects
                .exclude(email__isnull=True).exclude(email='')
                .filter(email__contains='@')
                .select_related('comuna')
                .annotate(ultima_compra=Max('ventareserva__fecha_reserva'))
                .order_by(F('ultima_compra').desc(nulls_last=True), '-id'))

    vistos, fila = set(), []
    for c in clientes.iterator():
        email = (c.email or '').strip().lower()
        if (not _email_valido(email) or email in vistos or email in bajas
                or email in esperando or email in recientes):
            continue
        vistos.add(email)
        fila.append({'cliente': c, 'email': email})
    return fila


def _crear_campana(nombre, asunto, cuerpo, destinatarios, descripcion):
    campana = EmailCampaign.objects.create(
        name=nombre, description=descripcion, status='draft',
        email_subject_template=asunto, email_body_template=cuerpo,
        ai_variation_enabled=False,        # SIEMPRE: la IA reescribe y rompe el HTML
        anti_spam_enabled=True,
        schedule_config=dict(SCHEDULE),
        criteria={'origen': 'api_campana_semanal',
                  'regla': 'todos con correo · última compra desc · sin correo en 28 días',
                  'tope': TOPE_LOTE},
        total_recipients=len(destinatarios))
    filas = []
    for d in destinatarios:
        c = d['cliente']
        primer = _primer_nombre(c.nombre)
        ubicacion = c.comuna.nombre if c.comuna_id else (c.ciudad or 'N/A')
        filas.append(EmailRecipient(
            campaign=campana, client=c, email=d['email'], name=primer,
            personalized_subject=asunto.replace('{nombre_cliente}', primer),
            personalized_body=cuerpo.replace('{nombre_cliente}', primer),
            client_city=ubicacion))
    EmailRecipient.objects.bulk_create(filas, batch_size=500)
    return campana


def _resumen(c: EmailCampaign) -> dict:
    return {'id': c.id, 'nombre': c.name, 'destinatarios': c.total_recipients,
            'estado': c.status,
            'revisar_en': BASE_PUBLICA + reverse('admin:ventas_emailcampaign_change',
                                                 args=[c.id])}


def _existentes(nombre):
    return list(EmailCampaign.objects
                .filter(Q(name=nombre) | Q(name__startswith=f'{nombre} · lote '))
                .order_by('id'))


@csrf_exempt
@require_http_methods(['POST'])
def crear(request):
    if not _api_key_ok(request):
        return JsonResponse({'error': 'X-API-KEY inválida o ausente'}, status=401)
    try:
        datos = json.loads(request.body or b'{}')
        if not isinstance(datos, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return _error('El cuerpo de la llamada no es JSON válido.')

    asunto = str(datos.get('asunto') or '').strip()
    cuerpo = str(datos.get('cuerpo_html') or '')
    if not asunto:
        return _error('Falta el asunto.')
    if len(asunto) > MAX_ASUNTO:
        return _error(f'El asunto supera los {MAX_ASUNTO} caracteres.')
    if not cuerpo.strip():
        return _error('Falta el cuerpo HTML.')
    if len(cuerpo.encode('utf-8')) > MAX_CUERPO_BYTES:
        return _error('El cuerpo supera los 100 KB: Gmail lo recortaría y escondería '
                      'el enlace de baja.')
    if '<script' in cuerpo.lower():
        return _error('El cuerpo no puede traer <script>.')
    segmento = str(datos.get('segmento') or '').strip().lower()
    if segmento not in SEGMENTOS_ACEPTADOS:
        return _error('El lote lo arma Aremko con todos los clientes con correo; no se '
                      f'acepta un segmento («{segmento}»). Omite el campo o manda "todos".')
    # Ojo: `or 1` convertiría lotes=0 en 1 (0 es falsy) y lo dejaría pasar.
    lotes_pedidos = datos.get('lotes')
    try:
        lotes = 1 if lotes_pedidos is None else int(lotes_pedidos)
    except (TypeError, ValueError):
        return _error('«lotes» debe ser un número entre 1 y 6.')
    if not 1 <= lotes <= MAX_LOTES:
        return _error(f'«lotes» debe estar entre 1 y {MAX_LOTES}.')

    hoy = timezone.localtime(timezone.now()).date().isoformat()
    nombre = str(datos.get('nombre') or '').strip() or f'Correo semanal {hoy}'
    origen = str(datos.get('origen') or 'api').strip()[:60]

    previas = _existentes(nombre)
    if previas:
        return JsonResponse({'ok': True, 'repetida': True,
                             'campanas': [_resumen(c) for c in previas]}, status=200)

    fila = fila_de_elegibles()
    if not fila:
        return _error('Nadie elegible hoy: todos los correos válidos están en baja, '
                      'esperando en otra campaña o recibieron uno hace menos de 28 días.')

    rebanadas = [fila[i * TOPE_LOTE:(i + 1) * TOPE_LOTE] for i in range(lotes)]
    rebanadas = [r for r in rebanadas if r]
    n = len(rebanadas)
    creadas = []
    with transaction.atomic():
        for i, destinatarios in enumerate(rebanadas, start=1):
            nombre_lote = nombre if n == 1 else f'{nombre} · lote {i}/{n}'
            descripcion = (f'Creada por API ({origen}) el {hoy}. Lote {i} de {n}: los '
                           f'siguientes {len(destinatarios)} de la fila de {len(fila)} '
                           f'elegibles (última compra más reciente primero). Queda en '
                           f'Borrador hasta que alguien la pase a «Lista para envío».')
            creadas.append(_crear_campana(nombre_lote, asunto, cuerpo, destinatarios,
                                          descripcion))

    en_lote = sum(c.total_recipients for c in creadas)
    logger.warning('[campana-semanal] %s creó %d campaña(s) «%s»: %d destinatarios de %d '
                   'elegibles', origen, n, nombre, en_lote, len(fila))
    return JsonResponse({'ok': True, 'repetida': False,
                         'campanas': [_resumen(c) for c in creadas],
                         'universo': len(fila), 'sin_lote': len(fila) - en_lote},
                        status=201)
