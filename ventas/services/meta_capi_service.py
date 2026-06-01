"""Meta Conversions API (CAPI) — eventos server-side a Meta Events Manager.

Complementa el Pixel client-side: el Pixel puede perderse si el cliente cierra
el navegador antes de cargar la pagina de retorno; CAPI garantiza que el evento
llegue porque se dispara desde el webhook server-to-server de Flow.cl.

Deduplicacion: Pixel y CAPI deben enviar el MISMO event_id para que Meta los
trate como un solo evento. Usamos event_id deterministico (purchase_<venta_id>,
lead_<pending_id>) para no requerir storage extra.

PII (email, telefono, nombre): hasheada SHA-256 minusculas/sin espacios, segun
requisito Meta.

Doc oficial: https://developers.facebook.com/docs/marketing-api/conversions-api
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_CAPI_TIMEOUT = 8  # segundos, no bloquear el webhook si Meta se demora


def _hash_pii(value: Optional[str]) -> Optional[str]:
    """SHA-256 de email/telefono/nombre en minusculas y sin espacios."""
    if not value:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    """Telefono solo digitos (Meta requiere E.164 sin +)."""
    if not phone:
        return None
    digits = "".join(ch for ch in phone if ch.isdigit())
    return digits or None


def _build_user_data(
    *,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    nombre: Optional[str] = None,
    apellido: Optional[str] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    fbp: Optional[str] = None,
    fbc: Optional[str] = None,
) -> dict:
    """Arma el bloque user_data con PII hasheada + identificadores de navegador."""
    user_data: dict = {}

    em = _hash_pii(email)
    if em:
        user_data["em"] = [em]

    ph = _hash_pii(_normalize_phone(phone))
    if ph:
        user_data["ph"] = [ph]

    fn = _hash_pii(nombre)
    if fn:
        user_data["fn"] = [fn]

    ln = _hash_pii(apellido)
    if ln:
        user_data["ln"] = [ln]

    if client_ip:
        user_data["client_ip_address"] = client_ip
    if user_agent:
        user_data["client_user_agent"] = user_agent
    if fbp:
        user_data["fbp"] = fbp
    if fbc:
        user_data["fbc"] = fbc

    return user_data


def _post_event(
    *,
    event_name: str,
    event_id: str,
    user_data: dict,
    custom_data: dict,
    event_source_url: Optional[str] = None,
) -> dict:
    """POST a /events del Pixel. Devuelve dict con status y respuesta de Meta."""
    pixel_id = settings.META_PIXEL_ID
    token = settings.META_CAPI_ACCESS_TOKEN
    api_version = getattr(settings, "META_CAPI_API_VERSION", "v21.0")

    if not pixel_id or not token:
        logger.warning(
            "Meta CAPI no configurado (META_PIXEL_ID o META_CAPI_ACCESS_TOKEN vacios). "
            "Evento %s omitido.",
            event_name,
        )
        return {"skipped": True, "reason": "missing_config"}

    payload: dict = {
        "data": [
            {
                "event_name": event_name,
                "event_time": int(time.time()),
                "event_id": event_id,
                "action_source": "website",
                "user_data": user_data,
                "custom_data": custom_data,
            }
        ],
        "access_token": token,
    }

    if event_source_url:
        payload["data"][0]["event_source_url"] = event_source_url

    test_code = getattr(settings, "META_CAPI_TEST_EVENT_CODE", "")
    if test_code:
        payload["test_event_code"] = test_code

    url = f"https://graph.facebook.com/{api_version}/{pixel_id}/events"

    try:
        resp = requests.post(url, json=payload, timeout=_CAPI_TIMEOUT)
        body = resp.json() if resp.content else {}
        if resp.status_code >= 400:
            logger.error(
                "Meta CAPI error %s en evento %s (event_id=%s): %s",
                resp.status_code, event_name, event_id, body,
            )
            return {"ok": False, "status": resp.status_code, "body": body}
        logger.info(
            "Meta CAPI ok evento=%s event_id=%s response=%s",
            event_name, event_id, body,
        )
        return {"ok": True, "status": resp.status_code, "body": body}
    except requests.RequestException as exc:
        logger.error("Meta CAPI request fallo evento=%s event_id=%s: %s", event_name, event_id, exc)
        return {"ok": False, "error": str(exc)}


def send_purchase_event(
    *,
    venta_id: int,
    amount: float,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    nombre_completo: Optional[str] = None,
    content_ids: Optional[list] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    fbp: Optional[str] = None,
    fbc: Optional[str] = None,
    event_source_url: Optional[str] = None,
) -> dict:
    """Envia evento Purchase via CAPI tras confirmacion de pago Flow.

    event_id deterministico: purchase_<venta_id> — debe coincidir con el Pixel
    en flow_return.html para que Meta deduplique.
    """
    nombre = apellido = None
    if nombre_completo:
        partes = nombre_completo.strip().split(maxsplit=1)
        nombre = partes[0] if partes else None
        apellido = partes[1] if len(partes) > 1 else None

    user_data = _build_user_data(
        email=email, phone=phone, nombre=nombre, apellido=apellido,
        client_ip=client_ip, user_agent=user_agent, fbp=fbp, fbc=fbc,
    )

    custom_data = {
        "currency": "CLP",
        "value": float(amount or 0),
        "content_ids": content_ids or [str(venta_id)],
        "content_type": "product",
    }

    return _post_event(
        event_name="Purchase",
        event_id=f"purchase_{venta_id}",
        user_data=user_data,
        custom_data=custom_data,
        event_source_url=event_source_url,
    )


def send_schedule_event(
    *,
    pending_id: int,
    amount: float,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    nombre_completo: Optional[str] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    fbp: Optional[str] = None,
    fbc: Optional[str] = None,
    event_source_url: Optional[str] = None,
) -> dict:
    """Envia evento Schedule via CAPI al crear PendingReservation (reserva agendada,
    pago pendiente).

    Antes era 'Lead'; se cambio a 'Schedule' para dejar 'Lead' EXCLUSIVO del
    formulario Refugio. event_id deterministico: schedule_<pending_id> (debe
    coincidir con el Pixel client-side para deduplicar).
    """
    nombre = apellido = None
    if nombre_completo:
        partes = nombre_completo.strip().split(maxsplit=1)
        nombre = partes[0] if partes else None
        apellido = partes[1] if len(partes) > 1 else None

    user_data = _build_user_data(
        email=email, phone=phone, nombre=nombre, apellido=apellido,
        client_ip=client_ip, user_agent=user_agent, fbp=fbp, fbc=fbc,
    )

    custom_data = {
        "currency": "CLP",
        "value": float(amount or 0),
        "content_category": "reservation_pending",
    }

    return _post_event(
        event_name="Schedule",
        event_id=f"schedule_{pending_id}",
        user_data=user_data,
        custom_data=custom_data,
        event_source_url=event_source_url,
    )
