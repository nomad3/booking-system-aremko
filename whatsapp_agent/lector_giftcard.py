"""Leer la foto de una gift card que manda el cliente (P-52 paso 3, 25-09-2026).

Jorge: «normalmente el cliente solo manda la foto». Luna no veía imágenes —le
llegaban como «(image)»— y Deborah contestaba siempre lo mismo: «me envía
imagen de la gift card», «reviso el código», «disponible tina a las…».

Prueba real del 25-09 con el mismo modelo de Luna (Gemini 2.5 Flash, que ve
imágenes) sobre las 68 fotos de conversaciones de canje de 90 días: 10 de 10
gift cards del sistema leídas exactas; una copiada a mano con un carácter mal
(la búsqueda con tolerancia la encuentra: era la gift card 471); 4 vouchers
antiguos «R ####» bien leídos (el número es la reserva); 34 comprobantes y 19
otras fotos bien descartadas. Unos 2 segundos y US$0,0007 por foto.

Cada foto se lee UNA vez y queda en LecturaImagen. Nada de esto puede impedir
que Luna responda: ante cualquier falla, todo sigue como antes.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import time

logger = logging.getLogger(__name__)

MODELO_VISION = os.getenv('LUNA_MODELO_VISION', 'google/gemini-2.5-flash')
SEGUNDOS_MAXIMOS = 25
MAX_FOTOS_POR_TURNO = 3
# Una foto sin responder más vieja que esto ya no es «este turno».
DIAS_DEL_TURNO = 7
# Tras la foto, lo que el cliente escriba en estos días sigue siendo el canje.
DIAS_CANJE_EN_CURSO = 3
PALABRAS_MAX_TEXTO_NEUTRO = 10
TIPOS = ('giftcard_aremko', 'voucher_antiguo', 'comprobante', 'otro')
# Los que tocan el canje: el resto de las fotos sigue como hoy.
DE_CANJE = ('giftcard_aremko', 'voucher_antiguo')

# La MISMA instrucción de la prueba del 25-09 (no se toca sin volver a medir). Ahí
# los vouchers antiguos salieron como tipo gift card con código «R5602»: el
# voucher lo distingue el código (numero_de_voucher), no el modelo.
INSTRUCCION = (
    'Eres un lector de documentos. Mira la imagen y responde SOLO un JSON, sin texto extra: '
    '{"tipo": "giftcard_aremko" | "comprobante" | "otro", "codigo": "<12 letras y números o null>", '
    '"legible": true|false}. '
    'Una gift card de Aremko Spa Boutique dice "CERTIFICADO DE REGALO" o "GiftCard" y trae un código '
    'de 12 caracteres (bajo "TU CÓDIGO"). Copia el código exacto, sin espacios. Si no hay gift card de '
    'Aremko, codigo = null.')


def es_foto(msg):
    """Foto normal, o mandada «como documento» (sin comprimir). Los stickers no."""
    tipo = (msg.msg_type or '') if msg else ''
    return bool(msg) and bool(getattr(msg, 'media_file', None)) and tipo != 'sticker' and (
        tipo == 'image' or (msg.mime_type or '').startswith('image/'))


def _bytes_de(msg):
    with msg.media_file.open('rb') as fh:
        return fh.read()


def _preguntar_al_modelo(datos, mime):
    """(lo leído, tokens, milisegundos). Lanza si el modelo falla."""
    from django.conf import settings
    from openai import OpenAI

    cliente = OpenAI(base_url=settings.OPENROUTER_BASE_URL, api_key=settings.OPENROUTER_API_KEY,
                     timeout=SEGUNDOS_MAXIMOS)
    inicio = time.time()
    r = cliente.chat.completions.create(
        model=MODELO_VISION, temperature=0, max_tokens=150,
        messages=[{'role': 'user', 'content': [
            {'type': 'text', 'text': INSTRUCCION},
            {'type': 'image_url', 'image_url': {
                'url': f'data:{mime};base64,{base64.b64encode(datos).decode()}'}}]}])
    ms = int((time.time() - inicio) * 1000)
    texto = r.choices[0].message.content or ''
    m = re.search(r'\{.*\}', texto, re.S)
    leido = json.loads(m.group(0)) if m else {}
    uso = getattr(r, 'usage', None)
    tokens = ((getattr(uso, 'prompt_tokens', 0) or 0) + (getattr(uso, 'completion_tokens', 0) or 0))
    return leido, tokens, ms


def _estado_con_detalle(gc):
    """(estado en palabras, ¿se puede usar?)."""
    from ventas.models import Pago
    from ventas.services.giftcard_estado import estado_giftcard, pesos

    estado = estado_giftcard(gc)
    if estado == 'Vencida':
        return f'vencida el {gc.fecha_vencimiento:%d-%m-%Y}', False
    if estado == 'Usada':
        uso = (Pago.objects.filter(giftcard=gc, metodo_pago='giftcard')
               .order_by('-fecha_pago').values_list('venta_reserva_id', flat=True).first())
        return (f'ya usada en la reserva #{uso}' if uso else 'ya usada'), False
    if estado == 'Por cobrar':
        return f'por cobrar: la venta #{gc.venta_reserva_id} todavía debe', True
    if estado == 'Lista para usar':
        return f'lista para usar ({pesos(gc.monto_disponible)})', True
    return estado[:1].lower() + estado[1:], True


def describir_giftcard(gc, forma, leido=''):
    """«Pausa junto al río · código N7LT… · lista para usar ($90.000) · vence 22-09-2027»."""
    from ventas.services.giftcard_envio import nombre_experiencia
    from ventas.services.giftcard_estado import caracteres_distintos

    estado, usable = _estado_con_detalle(gc)
    partes = [nombre_experiencia(gc), f'código {gc.codigo}', estado]
    if usable and gc.fecha_vencimiento:
        partes.append(f'vence {gc.fecha_vencimiento:%d-%m-%Y}')
    if forma == 'tolerancia':
        n = caracteres_distintos(leido, gc.codigo) if leido else 1
        partes.append(f"la foto se leyó con {n} {'carácter' if n == 1 else 'caracteres'} de diferencia")
    return ' · '.join(partes)


def describir_voucher(numero):
    from ventas.models import VentaReserva

    venta = VentaReserva.objects.select_related('cliente').filter(pk=numero).first()
    if venta is None:
        return f'R {numero}: no existe la reserva #{numero}'
    return f'R {numero} → reserva #{numero} ({venta.cliente.nombre})'


def _identificar(leido):
    """(tipo, código, gift card, forma, voucher, resumen) a partir de lo leído."""
    from ventas.services.giftcard_estado import buscar_por_codigo, codigo_limpio, numero_de_voucher

    tipo = leido.get('tipo') if leido.get('tipo') in TIPOS else 'otro'
    crudo = str(leido.get('codigo') or '')
    if crudo.strip().lower() in ('null', 'none', 'n/a', '-'):
        crudo = ''
    codigo = codigo_limpio(crudo)
    voucher = numero_de_voucher(crudo) or numero_de_voucher(codigo)
    if tipo == 'voucher_antiguo' or (tipo == 'giftcard_aremko' and voucher):
        if not voucher:
            return 'voucher_antiguo', codigo, None, '', None, 'voucher antiguo sin número legible'
        return 'voucher_antiguo', codigo, None, '', voucher, describir_voucher(voucher)
    if tipo == 'giftcard_aremko':
        if not codigo:
            return tipo, '', None, '', None, 'foto de gift card, pero no se alcanza a leer el código'
        encontradas, forma = buscar_por_codigo(codigo)
        if len(encontradas) == 1 and forma:
            return tipo, codigo, encontradas[0], forma, None, describir_giftcard(encontradas[0], forma,
                                                                                 codigo)
        return tipo, codigo, None, '', None, f'el código leído ({codigo}) no está en el sistema'
    # Comprobantes y otras fotos: no se guarda nada de lo que dicen.
    return tipo, '', None, '', None, ''


def _como_dict(lectura):
    return {'tipo': lectura.tipo, 'codigo': lectura.codigo, 'giftcard_id': lectura.giftcard_id,
            'forma': lectura.forma, 'voucher': lectura.voucher, 'resumen': lectura.resumen,
            'tokens': lectura.tokens, 'latency_ms': lectura.latency_ms}


def leer(msg):
    """La lectura de esta foto (dict), o None si no es foto o no se pudo leer."""
    if not es_foto(msg):
        return None
    from .models import LecturaImagen

    try:
        previa = LecturaImagen.objects.filter(wa_message_id=msg.wa_message_id).first()
    except Exception:  # noqa: BLE001 — tabla todavía sin migrar: se lee sin guardar
        previa = None
    if previa is not None:
        return _como_dict(previa)
    try:
        leido, tokens, ms = _preguntar_al_modelo(_bytes_de(msg), msg.mime_type or 'image/jpeg')
    except Exception as exc:  # noqa: BLE001 — sin lectura, Luna sigue como antes
        logger.warning('[lector] no se pudo leer la foto %s: %s', msg.wa_message_id, exc)
        return None
    try:
        tipo, codigo, gc, forma, voucher, resumen = _identificar(leido if isinstance(leido, dict) else {})
    except Exception as exc:  # noqa: BLE001
        logger.warning('[lector] no se pudo identificar la foto %s: %s', msg.wa_message_id, exc)
        return None
    fila = {'tipo': tipo, 'codigo': codigo[:40], 'giftcard_id': gc.pk if gc else None,
            'forma': forma, 'voucher': voucher, 'resumen': resumen[:200],
            'tokens': tokens, 'latency_ms': ms}
    try:
        LecturaImagen.objects.update_or_create(
            wa_message_id=msg.wa_message_id,
            defaults={'phone': msg.phone, 'modelo': MODELO_VISION[:120], **fila})
    except Exception:  # noqa: BLE001
        logger.warning('[lector] no se pudo guardar la lectura de %s', msg.wa_message_id)
    logger.info('[lector] foto %s de …%s: %s %s', (msg.wa_message_id or '')[-8:], (msg.phone or '')[-4:],
                tipo, resumen[:80])
    return fila


def fotos_de_canje_pendientes(phone):
    """Las lecturas de gift card o voucher entre las fotos que el cliente mandó
    y nadie ha respondido todavía (la más reciente primero).

    No basta con mirar el último mensaje: el cliente manda la foto y después
    escribe «hola, quiero agendar con esta gift card», o al revés. Se leen a lo
    más las 3 fotos más recientes del turno; cada una se lee una sola vez.
    """
    from datetime import timedelta

    from django.db.models import Q
    from django.utils import timezone
    from ventas.models import WhatsAppMessage

    candidatas = (WhatsAppMessage.objects
                  .filter(phone=phone, direction='in', requiere_atencion=True,
                          timestamp__gte=timezone.now() - timedelta(days=DIAS_DEL_TURNO))
                  .filter(Q(msg_type='image') | Q(mime_type__startswith='image/'))
                  .exclude(msg_type='sticker').exclude(media_file='').exclude(media_file__isnull=True)
                  .order_by('-timestamp')[:MAX_FOTOS_POR_TURNO])
    lecturas = []
    for msg in candidatas:
        lectura = leer(msg)
        if lectura and lectura['tipo'] in DE_CANJE:
            lecturas.append(lectura)
    return lecturas


def motivo_para_deborah(lecturas):
    """Lo que Deborah ve en la bandeja («Derivar a persona. …») cuando el canje
    pasa a ella: la gift card ya identificada, para no pedir el código."""
    primera = lecturas[0]
    if primera['tipo'] == 'voucher_antiguo':
        motivo = f"Canje de voucher antiguo · {primera['resumen']}"
    else:
        motivo = f"Canje de gift card · {primera['resumen']}"
    extra = len(lecturas) - 1
    if extra:
        motivo += f" (y {extra} {'foto' if extra == 1 else 'fotos'} más de gift card)"
    return motivo


def lecturas_de(wa_message_ids):
    """{wa_message_id: resumen} de las fotos de canje ya leídas (para el historial)."""
    from .models import LecturaImagen

    try:
        return dict(LecturaImagen.objects
                    .filter(wa_message_id__in=list(wa_message_ids), tipo__in=DE_CANJE)
                    .values_list('wa_message_id', 'resumen'))
    except Exception:  # noqa: BLE001
        return {}



# --- Deploy 2a (25-09-2026): Luna da la bienvenida al canje -------------------
# Jorge aprobó el flujo: con la foto de una gift card que se puede usar, Luna
# saluda, confirma cuál es y pide el día; Deborah sigue confirmando todo. Lo que
# el cliente responda después (el día, la hora) todavía lo ve Deborah: buscar el
# horario con la ficha de cada gift card es el deploy 2b.

_FECHA_U_HORA = re.compile(
    r'\d|\b(hoy|mañana|manana|pasado|lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|'
    r'domingo|finde|fin de semana|semana|enero|febrero|marzo|abril|mayo|junio|julio|agosto|'
    r'septiembre|setiembre|octubre|noviembre|diciembre)\b', re.IGNORECASE)

_MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
          'septiembre', 'octubre', 'noviembre', 'diciembre')

# Los mismos saludos que Luna usa en el prompt (prompt.bloque_saludo).
_SALUDOS = {
    'primer_contacto': '¡Hola{voc}! 🌿 Te saluda Luna, tu asistente en Aremko Spa Boutique.',
    'regreso': '¡Hola{voc}! 🌿 Te saluda Luna, de Aremko. ¡Qué gusto tenerte de vuelta!',
}


def texto_neutro(texto):
    """¿Este mensaje se contesta bien con la bienvenida? Un saludo o «me
    regalaron esta gift card» sí. Una fecha, una hora, una pregunta o un
    mensaje largo no: eso lo ve Deborah."""
    t = (texto or '').strip()
    if not t:
        return True
    return ('?' not in t and '¿' not in t and not _FECHA_U_HORA.search(t)
            and len(t.split()) <= PALABRAS_MAX_TEXTO_NEUTRO)


def se_puede_usar(gc):
    from ventas.services.giftcard_estado import estado_giftcard

    estado = estado_giftcard(gc)
    return estado == 'Lista para usar' or estado.startswith('Le quedan')


def _fecha_larga(fecha):
    return f'{fecha.day} de {_MESES[fecha.month - 1]} de {fecha.year}'


def bienvenida_de_canje(gc, saludo_estado='', nombre=''):
    """El borrador para quien manda la foto de una gift card que se puede usar:
    saluda como Luna, confirma cuál es y pide el día. Texto fijo, sin modelo."""
    from ventas.services.giftcard_envio import nombre_experiencia
    from ventas.services.giftcard_estado import pesos

    saldo = int(gc.monto_disponible or 0)
    vence = f' hasta el {_fecha_larga(gc.fecha_vencimiento)}' if gc.fecha_vencimiento else ''
    if (gc.servicio_asociado or '').strip() in ('', 'monto_libre'):
        cual = f'tu gift card de {pesos(gc.monto_inicial)}'
    else:
        cual = f'tu gift card «{nombre_experiencia(gc)}»'
    if saldo < int(gc.monto_inicial or 0):
        estado = f'Le quedan {pesos(saldo)} por usar{vence}.'
    else:
        estado = f'Está lista para usar{vence}.'
    partes = []
    saludo = _SALUDOS.get(saludo_estado)
    if saludo:
        partes.append(saludo.format(voc=f', {nombre}' if nombre else ''))
    partes.append(f'Recibí {cual} 🎁 {estado}')
    partes.append('¿Qué día te gustaría venir? Te busco el horario.')
    return '\n\n'.join(partes)


def canje_en_curso(phone):
    """La gift card que este cliente mandó en foto en los últimos días y que
    todavía se puede usar, con su descripción para Deborah; o None."""
    from datetime import timedelta

    from django.utils import timezone
    from ventas.models import GiftCard

    from .models import LecturaImagen

    try:
        lectura = (LecturaImagen.objects
                   .filter(phone=phone, tipo='giftcard_aremko', giftcard_id__isnull=False,
                           created_at__gte=timezone.now() - timedelta(days=DIAS_CANJE_EN_CURSO))
                   .order_by('-created_at').first())
    except Exception:  # noqa: BLE001 — tabla sin migrar
        return None
    if lectura is None:
        return None
    gc = GiftCard.objects.filter(pk=lectura.giftcard_id).first()
    if gc is None or not se_puede_usar(gc):
        return None
    return {'giftcard': gc, 'resumen': describir_giftcard(gc, lectura.forma, lectura.codigo)}
