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
from django.utils import timezone

logger = logging.getLogger(__name__)

RESERVAR_URL = "https://www.aremko.cl/masajes/"

# (tipo_email, offset desde que se completa la ficha, es_comercial)
CADENCIA = [
    ('gracias_visita',    timedelta(hours=24), False),
    ('seguimiento_7d',    timedelta(days=7),   True),
    ('recomendacion_30d', timedelta(days=30),  True),
    ('reactivacion_60d',  timedelta(days=60),  True),
    ('reactivacion_90d',  timedelta(days=90),  True),
]

FIRMA = "\n\nCon cariño,\nEquipo Aremko · Puerto Varas"


def _contenido(tipo, nombre):
    """Devuelve (asunto, cuerpo_texto) borrador por tipo. Editable: estos textos
    son un punto de partida; revisar antes de activar el envío."""
    n = nombre or ""
    saludo = f"Hola {n}," if n else "Hola,"
    if tipo == 'gracias_visita':
        return (
            "Gracias por tu momento de bienestar en Aremko 🌿",
            f"{saludo}\n\nGracias por darte un espacio para ti en Aremko. Esperamos "
            f"que hayas salido más relajado/a y en calma.\n\nSi quieres contarnos "
            f"cómo te sentiste, nos encanta leerte: solo responde este correo." + FIRMA,
        )
    if tipo == 'seguimiento_7d':
        return (
            "¿Cómo te has sentido esta semana? 🌿",
            f"{saludo}\n\nYa pasó una semana de tu masaje. Muchas personas notan que "
            f"el bienestar se cuida mejor con cierta frecuencia. Si quieres mantener "
            f"esa sensación de calma, podemos reservarte un próximo espacio cuando te "
            f"acomode.\n\nReserva aquí: {RESERVAR_URL}" + FIRMA,
        )
    if tipo == 'recomendacion_30d':
        return (
            "Un mes de bienestar: tu próximo espacio te espera 🌿",
            f"{saludo}\n\nHa pasado un mes desde tu visita. Si sentiste que ese rato "
            f"de pausa te hizo bien, este puede ser un buen momento para repetirlo.\n\n"
            f"Te dejamos el link para elegir día y hora: {RESERVAR_URL}" + FIRMA,
        )
    if tipo == 'reactivacion_60d':
        return (
            "Te echamos de menos en Aremko 🌿",
            f"{saludo}\n\nHace un par de meses que no te vemos. Tu bienestar nos "
            f"importa: si quieres regalarte de nuevo una pausa de masaje, aquí "
            f"estamos para recibirte.\n\nReserva tu espacio: {RESERVAR_URL}" + FIRMA,
        )
    if tipo == 'reactivacion_90d':
        return (
            "Un espacio para reencontrarte con tu calma 🌿",
            f"{saludo}\n\nYa han pasado unos meses desde tu última visita. Cuando "
            f"sientas que necesitas un respiro, en Aremko te tenemos un lugar "
            f"tranquilo y a tu ritmo.\n\nReserva cuando quieras: {RESERVAR_URL}" + FIRMA,
        )
    return ("Aremko", f"{saludo}\n\nGracias por visitarnos." + FIRMA)


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
        "Queremos compartirte un breve resumen de tu experiencia de bienestar en Aremko:",
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
        f"Cuando quieras volver a darte este espacio, reserva aquí: {RESERVAR_URL}",
        FIRMA.strip(),
    ]
    return ("Tu resumen de bienestar en Aremko 🌿", "\n".join(lineas))


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


def enviar_seguimiento(seg):
    """Envía un SeguimientoBienestarMasaje por email. Marca estado. Devuelve bool."""
    from django.core.mail import EmailMultiAlternatives

    email = (seg.participante.email if seg.participante_id else '') or \
            (seg.cliente.email if seg.cliente_id else '') or ''
    email = email.strip()
    if not email:
        seg.estado = 'error'
        seg.error_log = 'Sin email de destino'
        seg.save(update_fields=['estado', 'error_log'])
        return False
    try:
        texto = seg.cuerpo or ''
        html = ('<div style="font-family:Arial,sans-serif;font-size:15px;color:#333;'
                'line-height:1.5;">' + texto.replace('\n', '<br>') + '</div>')
        msg = EmailMultiAlternatives(
            subject=seg.asunto or 'Aremko',
            body=texto,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'comunicaciones@aremko.cl'),
            to=[email],
        )
        msg.attach_alternative(html, "text/html")
        msg.send()
        seg.estado = 'enviado'
        seg.fecha_envio = timezone.now()
        seg.save(update_fields=['estado', 'fecha_envio'])
        return True
    except Exception as exc:
        seg.estado = 'error'
        seg.error_log = str(exc)[:2000]
        seg.save(update_fields=['estado', 'error_log'])
        logger.warning("[Masajes] Error enviando seguimiento %s: %s", seg.id, exc)
        return False


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
