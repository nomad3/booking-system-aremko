"""Mensaje de ausencia (H-008) — auto-respuesta fija con guard anti-spam.

Cuando `ausencia_activa=True`, a cada entrante de texto se le responde una frase
fija (deriva a www.aremko.cl), a lo más una vez por conversación cada
`ausencia_anti_spam_horas`. El envío real lo hace el Go de aremko-cli (Django
devuelve una directiva en la respuesta del inbound); acá se decide y se registra.
"""

import logging

logger = logging.getLogger(__name__)


def debe_enviar(ultimo_envio, ahora, horas):
    """Pura: ¿toca enviar la frase de ausencia? (anti-spam por ventana de horas).

    - Sin envío previo → True.
    - horas <= 0 → siempre True (responder a cada mensaje).
    - Si el último envío fue hace >= `horas` → True; si no, False.
    """
    if ultimo_envio is None:
        return True
    if not horas or horas <= 0:
        return True
    delta_horas = (ahora - ultimo_envio).total_seconds() / 3600.0
    return delta_horas >= horas


def evaluar_ausencia(config, phone):
    """Devuelve el texto de ausencia a enviar, o None.

    None si: la ausencia está inactiva, no hay mensaje configurado, o el guard
    anti-spam suprime (ya se respondió hace poco). Cuando devuelve texto, registra
    el envío (update_or_create) para la próxima ventana.
    """
    if not config.ausencia_activa:
        return None
    mensaje = (config.ausencia_mensaje or '').strip()
    if not mensaje:
        return None

    from django.utils import timezone

    from .models import AusenciaEnviada

    ahora = timezone.now()
    registro = AusenciaEnviada.objects.filter(phone=phone[:20]).first()
    ultimo = registro.ultimo_envio if registro else None

    if not debe_enviar(ultimo, ahora, config.ausencia_anti_spam_horas):
        return None

    # Registrar el envío (optimista: si el Go falla, no reintenta en la ventana;
    # es un mensaje de cortesía, riesgo bajo).
    try:
        AusenciaEnviada.objects.update_or_create(
            phone=phone[:20], defaults={'ultimo_envio': ahora},
        )
    except Exception:  # noqa: BLE001 — registrar no debe romper el inbound
        logger.exception('Ausencia: no se pudo registrar el envío para %s', phone)

    return mensaje
