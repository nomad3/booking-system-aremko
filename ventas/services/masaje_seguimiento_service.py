"""Conexión-Masajes — F6: programación y envío de emails de seguimiento.

Al completar la ficha de bienestar de un participante se PROGRAMAN los
SeguimientoBienestarMasaje (cadencia post-visita). El envío real lo hace el
comando `enviar_seguimientos_masaje` (cron) — y solo si
settings.MASAJE_SEGUIMIENTOS_ACTIVOS = True (apagado por defecto, para no enviar
a clientes reales hasta revisar los textos).

Cumplimiento:
- Lenguaje de bienestar, NUNCA médico (sin diagnóstico/tratamiento).
- Emails COMERCIALES (invitaciones/recomendaciones) solo si la ficha tiene
  consentimiento_marketing=True. El transaccional de agradecimiento puede ir
  igual, sin promoción.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.utils import timezone

logger = logging.getLogger(__name__)

BASE_URL = "https://www.aremko.cl"
RESERVAR_URL = f"{BASE_URL}/masajes/"

# Token firmado para la baja de comunicaciones (no requiere migración ni guardar
# el token: codifica el id del cliente y se valida con la SECRET_KEY).
BAJA_SALT = "baja-comunicaciones-masaje"


def baja_token(cliente_id):
    """Token firmado (cliente_id) para el enlace de baja de comunicaciones."""
    return signing.dumps(int(cliente_id), salt=BAJA_SALT)


def baja_url(cliente_id):
    """URL absoluta de baja para un cliente. None si no hay cliente."""
    if not cliente_id:
        return None
    return f"{BASE_URL}/masaje/baja/{baja_token(cliente_id)}/"


def cliente_acepta_email(cliente):
    """False solo si el cliente se dio de baja explícitamente (preferences)."""
    if cliente is None:
        return True  # sin cliente no podemos verificar; el participante igual tiene email
    prefs = getattr(cliente, 'preferences', None)
    if prefs is not None and not prefs.accepts_email:
        return False
    return True

# (tipo_email, offset desde que se completa la ficha, es_comercial)
CADENCIA = [
    ('gracias_visita',    timedelta(hours=24), False),
    ('seguimiento_7d',    timedelta(days=7),   True),
    ('recomendacion_30d', timedelta(days=30),  True),
    ('reactivacion_60d',  timedelta(days=60),  True),
    ('reactivacion_90d',  timedelta(days=90),  True),
]

FIRMA = "\n\nCon cariño,\nEquipo Aremko Spa Boutique · Puerto Varas"


def _contenido(tipo, nombre):
    """Devuelve (asunto, cuerpo) por tipo. El cuerpo es solo el MENSAJE (sin link
    ni firma): el botón "Reservar" y la firma se agregan al renderizar el email."""
    n = nombre or ""
    saludo = f"Hola {n}," if n else "Hola,"
    if tipo == 'gracias_visita':
        return (
            "Gracias por tu momento de bienestar en Aremko Spa Boutique 🌿",
            f"{saludo}\n\nGracias por darte un espacio para ti en Aremko Spa Boutique. "
            f"Esperamos que hayas salido más relajado/a y en calma.\n\nSi quieres contarnos "
            f"cómo te sentiste, nos encanta leerte: solo responde este correo.",
        )
    if tipo == 'seguimiento_7d':
        return (
            "¿Cómo te has sentido esta semana? 🌿",
            f"{saludo}\n\nYa pasó una semana de tu masaje. Muchas personas notan que "
            f"el bienestar se cuida mejor con cierta frecuencia. Si quieres mantener "
            f"esa sensación de calma, podemos reservarte un próximo espacio cuando te "
            f"acomode.",
        )
    if tipo == 'recomendacion_30d':
        return (
            "Un mes de bienestar: tu próximo espacio te espera 🌿",
            f"{saludo}\n\nHa pasado un mes desde tu visita. Si sentiste que ese rato "
            f"de pausa te hizo bien, este puede ser un buen momento para repetirlo.",
        )
    if tipo == 'reactivacion_60d':
        return (
            "Te echamos de menos en Aremko Spa Boutique 🌿",
            f"{saludo}\n\nHace un par de meses que no te vemos. Tu bienestar nos "
            f"importa: si quieres regalarte de nuevo una pausa de masaje, aquí "
            f"estamos para recibirte.",
        )
    if tipo == 'reactivacion_90d':
        return (
            "Un espacio para reencontrarte con tu calma 🌿",
            f"{saludo}\n\nYa han pasado unos meses desde tu última visita. Cuando "
            f"sientas que necesitas un respiro, en Aremko Spa Boutique te tenemos un "
            f"lugar tranquilo y a tu ritmo.",
        )
    return ("Aremko Spa Boutique", f"{saludo}\n\nGracias por visitarnos.")


def _render_html(cuerpo, cta_label=None, url_baja=None):
    """Envuelve el mensaje en una plantilla HTML de marca (header + cuerpo +
    botón opcional + footer). El botón oculta el link de reserva. Si se pasa
    url_baja, el footer incluye el enlace para no recibir más comunicaciones."""
    cuerpo_html = (cuerpo or '').replace('\n', '<br>')
    boton = ''
    if cta_label:
        boton = (
            '<div style="text-align:center;margin:28px 0 6px;">'
            f'<a href="{RESERVAR_URL}" style="background:#b5651d;color:#ffffff;'
            'text-decoration:none;padding:14px 30px;border-radius:10px;font-weight:bold;'
            f'font-size:16px;display:inline-block;">{cta_label}</a></div>'
        )
    baja = ''
    if url_baja:
        baja = (
            '<div style="text-align:center;margin:14px 0 4px;">'
            f'<a href="{url_baja}" style="background:#b5651d;color:#ffffff;'
            'text-decoration:none;padding:14px 30px;border-radius:10px;font-weight:bold;'
            'font-size:16px;display:inline-block;">'
            'No recibir más comunicaciones</a></div>'
        )
    return (
        '<div style="background:#faf6f0;padding:24px 12px;'
        'font-family:Arial,Helvetica,sans-serif;">'
        '<div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:16px;'
        'overflow:hidden;border:1px solid #eee3d4;">'
        '<div style="background:#b5651d;padding:22px;text-align:center;">'
        '<div style="color:#ffffff;font-size:22px;font-weight:bold;">🌿 Aremko Spa Boutique</div>'
        '<div style="color:#f6e9da;font-size:13px;margin-top:2px;">Puerto Varas</div>'
        '</div>'
        '<div style="padding:26px 24px;color:#3a3a3a;font-size:16px;line-height:1.6;">'
        f'{cuerpo_html}{boton}{baja}'
        '</div>'
        '<div style="padding:16px 24px;background:#faf6f0;color:#999;font-size:12px;'
        'text-align:center;border-top:1px solid #eee3d4;">'
        'Con cariño, Equipo Aremko Spa Boutique · Puerto Varas<br>'
        '<a href="https://www.aremko.cl" style="color:#b5651d;">aremko.cl</a>'
        '</div></div></div>'
    )


CAMPOS_RESUMEN_TERAPEUTA = (
    'obs_terapeuta', 'zonas_trabajadas', 'intensidad_aplicada',
    'sugerencia_frecuencia', 'recomendacion_texto',
)


def ficha_tiene_resumen_terapeuta(ficha):
    """True si la masajista ya cargó al menos un campo del resumen del terapeuta."""
    return any((getattr(ficha, c, '') or '').strip() for c in CAMPOS_RESUMEN_TERAPEUTA)


def _contenido_resumen(ficha, nombre):
    """Email 'resumen de bienestar' (F7) armado con lo que cargó la masajista.
    Transaccional (informa sobre la propia sesión) + CTA suave a reservar.
    Lenguaje de bienestar, NUNCA médico."""
    n = nombre or ""
    saludo = f"Hola {n}," if n else "Hola,"
    lineas = [
        saludo,
        "",
        "Queremos compartirte un breve resumen de tu experiencia de bienestar en Aremko Spa Boutique:",
        "",
    ]
    if (ficha.zonas_trabajadas or '').strip():
        lineas.append(f"• Zonas trabajadas: {ficha.zonas_trabajadas.strip()}")
    if (ficha.intensidad_aplicada or '').strip():
        lineas.append(f"• Intensidad aplicada: {ficha.intensidad_aplicada.strip()}")
    if (ficha.obs_terapeuta or '').strip():
        lineas.append(f"• Observaciones: {ficha.obs_terapeuta.strip()}")
    if (ficha.sugerencia_frecuencia or '').strip():
        lineas.append(f"• Sugerencia de frecuencia: {ficha.sugerencia_frecuencia.strip()}")
    if (ficha.recomendacion_texto or '').strip():
        lineas.append("")
        lineas.append(ficha.recomendacion_texto.strip())
    lineas += [
        "",
        "Cuando quieras volver a darte este espacio, reserva con nosotros.",
    ]
    return ("Tu resumen de bienestar en Aremko Spa Boutique 🌿", "\n".join(lineas))


def programar_resumen_bienestar(ficha):
    """Programa (inmediato) el email de resumen cuando la masajista completa su
    resumen. Idempotente: un solo 'resumen_bienestar' por participante. Devuelve
    el Seguimiento creado o None."""
    from ..models import SeguimientoBienestarMasaje

    if not ficha_tiene_resumen_terapeuta(ficha):
        return None
    participante = getattr(ficha, 'participante', None)  # OneToOne reverse
    if participante is None:
        return None
    if SeguimientoBienestarMasaje.objects.filter(
        participante=participante, tipo_email='resumen_bienestar',
    ).exists():
        return None

    cliente = participante.cliente or getattr(ficha, 'cliente', None)
    email = (participante.email or getattr(ficha, 'email', '') or
             (cliente.email if cliente else '') or '').strip()
    if not email:
        return None

    nombre = ((participante.nombre or (cliente.nombre if cliente else '') or '')
              .strip().split(' ')[0])
    asunto, cuerpo = _contenido_resumen(ficha, nombre)
    seg = SeguimientoBienestarMasaje.objects.create(
        participante=participante,
        reserva=participante.reserva,
        cliente=cliente,
        tipo_email='resumen_bienestar',
        fecha_programada=timezone.now(),
        asunto=asunto,
        cuerpo=cuerpo,
        estado='pendiente',
    )
    logger.info("[Masajes] Resumen de bienestar programado para participante %s", participante.id)
    return seg


def programar_seguimientos_masaje(participante):
    """Crea los SeguimientoBienestarMasaje pendientes para el participante (al
    completar su ficha). Idempotente por (participante, tipo_email). Comerciales
    solo si la ficha tiene consentimiento_marketing. Devuelve los creados."""
    from ..models import SeguimientoBienestarMasaje

    ficha = getattr(participante, 'ficha_bienestar', None)
    if ficha is None:
        return []

    cliente = participante.cliente or getattr(ficha, 'cliente', None)
    email = (participante.email or getattr(ficha, 'email', '') or
             (cliente.email if cliente else '') or '').strip()
    if not email:
        return []  # sin email no hay seguimiento posible

    consent_mkt = bool(getattr(ficha, 'consentimiento_marketing', False))
    nombre = ((participante.nombre or (cliente.nombre if cliente else '') or '')
              .strip().split(' ')[0])
    ahora = timezone.now()

    creados = []
    for tipo, offset, comercial in CADENCIA:
        if comercial and not consent_mkt:
            continue
        if SeguimientoBienestarMasaje.objects.filter(
            participante=participante, tipo_email=tipo,
        ).exists():
            continue
        asunto, cuerpo = _contenido(tipo, nombre)
        creados.append(SeguimientoBienestarMasaje.objects.create(
            participante=participante,
            reserva=participante.reserva,
            cliente=cliente,
            tipo_email=tipo,
            fecha_programada=ahora + offset,
            asunto=asunto,
            cuerpo=cuerpo,
            estado='pendiente',
        ))
    if creados:
        logger.info("[Masajes] %d seguimiento(s) programado(s) para participante %s",
                    len(creados), participante.id)
    return creados


def enviar_seguimiento(seg, operador=''):
    """Envía un SeguimientoBienestarMasaje por email. Marca estado. Devuelve bool.
    operador: quién dispara el envío (bandeja de salida en aremko-cli)."""
    from django.core.mail import EmailMultiAlternatives

    cliente = (seg.participante.cliente if seg.participante_id else None) or \
              (seg.cliente if seg.cliente_id else None)

    # Respetar la baja: si el cliente se dio de baja, no enviar.
    if not cliente_acepta_email(cliente):
        seg.estado = 'cancelado'
        seg.error_log = 'Cliente se dio de baja de las comunicaciones'
        seg.save(update_fields=['estado', 'error_log'])
        return False

    email = (seg.participante.email if seg.participante_id else '') or \
            (seg.cliente.email if seg.cliente_id else '') or ''
    email = email.strip()
    if not email:
        seg.estado = 'error'
        seg.error_log = 'Sin email de destino'
        seg.save(update_fields=['estado', 'error_log'])
        return False
    try:
        cuerpo = seg.cuerpo or ''
        # CTA "Reservar" en todos salvo el de agradecimiento.
        con_cta = seg.tipo_email != 'gracias_visita'
        url_baja = baja_url(cliente.id if cliente else None)
        texto = cuerpo
        if con_cta:
            texto += f"\n\nReserva tu masaje: {RESERVAR_URL}"
        texto += FIRMA
        if url_baja:
            texto += (f"\n\n---\nSi no deseas recibir más correos ni WhatsApp con "
                      f"información, date de baja aquí: {url_baja}")
        html = _render_html(cuerpo, 'Reservar mi masaje' if con_cta else None, url_baja=url_baja)
        from_email = getattr(settings, 'MASAJE_FROM_EMAIL', None) or \
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'ventas@aremko.cl')
        msg = EmailMultiAlternatives(
            subject=seg.asunto or 'Aremko Spa Boutique',
            body=texto,
            from_email=from_email,
            to=[email],
        )
        msg.attach_alternative(html, "text/html")
        msg.send()
        seg.estado = 'enviado'
        seg.fecha_envio = timezone.now()
        if operador:
            seg.enviado_por = operador[:80]
        seg.save(update_fields=['estado', 'fecha_envio', 'enviado_por'])
        return True
    except Exception as exc:
        seg.estado = 'error'
        seg.error_log = str(exc)[:2000]
        seg.save(update_fields=['estado', 'error_log'])
        logger.warning("[Masajes] Error enviando seguimiento %s: %s", seg.id, exc)
        return False


def construir_html_preview(seg):
    """HTML final tal cual se enviaría (para la vista previa de la bandeja de
    salida en aremko-cli). Mismo render que enviar_seguimiento."""
    cliente = (seg.participante.cliente if seg.participante_id else None) or \
              (seg.cliente if seg.cliente_id else None)
    con_cta = seg.tipo_email != 'gracias_visita'
    url_b = baja_url(cliente.id if cliente else None)
    return _render_html(seg.cuerpo or '', 'Reservar mi masaje' if con_cta else None, url_baja=url_b)


def procesar_seguimientos_pendientes():
    """Envía los seguimientos pendientes ya vencidos. APAGADO por defecto:
    requiere settings.MASAJE_SEGUIMIENTOS_ACTIVOS=True para enviar de verdad."""
    from ..models import SeguimientoBienestarMasaje

    due_qs = SeguimientoBienestarMasaje.objects.filter(
        estado='pendiente', fecha_programada__lte=timezone.now(),
    )
    if not getattr(settings, 'MASAJE_SEGUIMIENTOS_ACTIVOS', False):
        return {'activo': False, 'enviados': 0, 'errores': 0,
                'pendientes_vencidos': due_qs.count()}

    enviados = errores = 0
    for seg in due_qs.select_related('participante', 'cliente'):
        if enviar_seguimiento(seg):
            enviados += 1
        else:
            errores += 1
    return {'activo': True, 'enviados': enviados, 'errores': errores}
