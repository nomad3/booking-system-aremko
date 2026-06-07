"""Conexión-Masajes — envío automático del link de ficha al confirmar el pago.

Al quedar pagada/parcial una reserva con masaje (y con la visita a futuro), se
envía UN correo al comprador con:
  - el link de su propia ficha de bienestar, y
  - el/los link(s) de ficha de su(s) acompañante(s), para que los comparta.

Idempotente por `comprador.estado_contacto` (no reenvía). Defensivo: nunca rompe
el guardado de la reserva (el caller lo envuelve en try/except).
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

BASE_URL = "https://www.aremko.cl"


def _ficha_url(token):
    return f"{BASE_URL}{reverse('masaje_ficha', kwargs={'token': token})}"


def _boton(url, label):
    return (
        '<div style="text-align:center;margin:18px 0 4px;">'
        f'<a href="{url}" style="background:#b5651d;color:#ffffff;text-decoration:none;'
        'padding:14px 30px;border-radius:10px;font-weight:bold;font-size:16px;'
        f'display:inline-block;">{label}</a></div>'
    )


def _enlace_copiable(url):
    """Muestra la URL como texto seleccionable (para copiar y reenviar), no como
    botón —un botón no se puede copiar fácil desde el correo."""
    return (
        '<div style="margin:8px 0 16px;padding:12px 14px;background:#faf6f0;'
        'border:1px dashed #d9c7b5;border-radius:8px;word-break:break-all;font-size:14px;">'
        f'<a href="{url}" style="color:#8a6d5a;">{url}</a></div>'
    )


def _render_html(cuerpo_html):
    return (
        '<div style="background:#faf6f0;padding:24px 12px;font-family:Arial,Helvetica,sans-serif;">'
        '<div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:16px;'
        'overflow:hidden;border:1px solid #eee3d4;">'
        '<div style="background:#b5651d;padding:22px;text-align:center;">'
        '<div style="color:#ffffff;font-size:22px;font-weight:bold;">🌿 Aremko Spa Boutique</div>'
        '<div style="color:#f6e9da;font-size:13px;margin-top:2px;">Puerto Varas</div></div>'
        '<div style="padding:26px 24px;color:#3a3a3a;font-size:16px;line-height:1.6;">'
        f'{cuerpo_html}</div>'
        '<div style="padding:16px 24px;background:#faf6f0;color:#999;font-size:12px;'
        'text-align:center;border-top:1px solid #eee3d4;">'
        'Con cariño, Equipo Aremko Spa Boutique · Puerto Varas<br>'
        '<a href="https://www.aremko.cl" style="color:#b5651d;">aremko.cl</a>'
        '</div></div></div>'
    )


def _tiene_masaje_futuro(venta):
    hoy = timezone.localdate()
    return venta.reservaservicios.filter(
        servicio__tipo_servicio='masaje', fecha_agendamiento__gte=hoy,
    ).exists()


def enviar_invitacion_ficha_reserva(venta):
    """Envía al comprador el link de su ficha + el de su(s) acompañante(s).
    Devuelve True si envió. Idempotente; solo si hay visita a futuro."""
    if not _tiene_masaje_futuro(venta):
        return False

    parts = list(venta.participantes_masaje.select_related('cliente').all())
    comprador = next((p for p in parts if p.tipo_participante == 'comprador'), None)
    if comprador is None:
        return False
    if comprador.estado_contacto not in ('pendiente', ''):
        return False  # ya se envió

    cli = comprador.cliente if comprador.cliente_id else getattr(venta, 'cliente', None)
    email = (comprador.email or (cli.email if cli else '') or '').strip()
    if not email:
        return False

    nombre = ((comprador.nombre or (cli.nombre if cli else '') or '')
              .strip().split(' ')[0])
    saludo = f"Hola {nombre}," if nombre else "Hola,"
    acompanantes = [p for p in parts if p.tipo_participante == 'acompanante']

    # --- Texto plano ---
    lineas = [
        saludo, "",
        "¡Gracias por reservar tu masaje en Aremko Spa Boutique! Para preparar tu "
        "experiencia, completa esta ficha breve de bienestar (1 minuto):",
        "", _ficha_url(comprador.token_formulario),
    ]
    if acompanantes:
        lineas += [
            "",
            "¿Vienes con acompañante? Copia y envíale este enlace por WhatsApp o "
            "correo para que complete su propia ficha (le pediremos su nombre, "
            "teléfono y email):",
        ]
        for a in acompanantes:
            lineas.append(_ficha_url(a.token_formulario))
    lineas += [
        "",
        "🔒 Tus datos se tratan con absoluta reserva y por ningún motivo se comparten con terceros.",
        "", "Con cariño,", "Equipo Aremko Spa Boutique · Puerto Varas",
    ]
    texto = "\n".join(lineas)

    # --- HTML ---
    cuerpo = [
        f'<p>{saludo}</p>',
        '<p>¡Gracias por reservar tu masaje en <b>Aremko Spa Boutique</b>! Para '
        'preparar tu experiencia, completa esta ficha breve de bienestar (1 minuto):</p>',
        _boton(_ficha_url(comprador.token_formulario), 'Completar mi ficha'),
    ]
    if acompanantes:
        cuerpo.append(
            '<p style="margin-top:20px;">¿Vienes con acompañante? '
            '<b>Copia y envíale este enlace</b> por WhatsApp o correo para que '
            'complete su propia ficha (le pediremos su nombre, teléfono y email):</p>')
        for a in acompanantes:
            cuerpo.append(_enlace_copiable(_ficha_url(a.token_formulario)))
    cuerpo.append(
        '<p style="margin-top:18px;font-size:13px;color:#777;">🔒 Tus datos se '
        'tratan con absoluta reserva y por ningún motivo se comparten con terceros.</p>')
    html = _render_html(''.join(cuerpo))

    from_email = (getattr(settings, 'MASAJE_FROM_EMAIL', None)
                  or getattr(settings, 'DEFAULT_FROM_EMAIL', 'ventas@aremko.cl'))
    msg = EmailMultiAlternatives(
        subject="Prepara tu masaje en Aremko Spa Boutique 🌿",
        body=texto, from_email=from_email, to=[email],
    )
    msg.attach_alternative(html, "text/html")
    msg.send()

    comprador.estado_contacto = 'email_enviado'
    comprador.fecha_envio = timezone.now()
    comprador.save(update_fields=['estado_contacto', 'fecha_envio', 'updated_at'])
    logger.info("[Masajes] Invitación de ficha enviada al comprador %s (reserva %s)",
                comprador.id, venta.id)
    return True
