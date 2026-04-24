import asyncio
import logging
from pathlib import Path
from typing import Optional

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)


class WAClient:
    """
    Gestor del cliente neonize. Encapsula:
    - arranque del cliente async como background task
    - captura de QR cuando no hay sesión
    - tracking de estado (conectado/desconectado/mensajes recibidos)
    - envío de mensajes

    Nota: la API exacta de neonize varía entre versiones. Este código usa los símbolos
    de neonize>=0.3.15. Si la versión instalada difiere, ajustar los imports y callbacks.
    """

    def __init__(self, session_path: str):
        self.session_path = session_path
        self._client = None
        self._connect_task: Optional[asyncio.Task] = None
        self._is_connected = False
        self._qr_data: Optional[str] = None
        self._messages_received = 0
        self._last_message_preview: Optional[str] = None
        self._last_error: Optional[str] = None

    def _register_handlers(self):
        """Registra handlers de eventos neonize. Importa dentro del método para evitar
        cargar neonize en tests que no lo necesitan."""
        from neonize.events import (
            ConnectedEv, DisconnectedEv, MessageEv, PairStatusEv,
        )

        @self._client.event(ConnectedEv)
        async def on_connected(_, ev):
            logger.info("WA connected")
            self._is_connected = True
            self._qr_data = None  # QR ya no es necesario

        @self._client.event(DisconnectedEv)
        async def on_disconnected(_, ev):
            logger.warning("WA disconnected: %r", ev)
            self._is_connected = False

        @self._client.event.qr
        async def on_qr(_, qr):
            # neonize >= 0.3.16: el QR viene via callback dedicado (client.event.qr),
            # con firma async (client, qr_bytes).
            try:
                code_str = qr.decode() if isinstance(qr, (bytes, bytearray)) else str(qr)
                self._qr_data = code_str
                logger.info("QR received (length=%d)", len(code_str))
            except Exception as e:
                logger.warning("QR extract failed: %s", e)

        @self._client.event(MessageEv)
        async def on_message(_, ev):
            self._messages_received += 1
            try:
                sender_jid = str(ev.Info.MessageSource.Sender)
            except Exception:
                sender_jid = "(unknown)"
            try:
                from_me = bool(getattr(ev.Info.MessageSource, "IsFromMe", False))
            except Exception:
                from_me = False
            try:
                message_id = str(getattr(ev.Info, "ID", "") or "")
            except Exception:
                message_id = ""
            try:
                ts = getattr(ev.Info, "Timestamp", None)
                timestamp = int(ts.timestamp()) if ts is not None and hasattr(ts, "timestamp") else int(ts or 0)
            except Exception:
                timestamp = 0
            text = ""
            try:
                msg = ev.Message
                if getattr(msg, "conversation", None):
                    text = msg.conversation
                elif getattr(msg, "extendedTextMessage", None) and getattr(msg.extendedTextMessage, "text", None):
                    text = msg.extendedTextMessage.text
            except Exception:
                text = "(unable to extract text)"
            self._last_message_preview = f"{sender_jid}: {text[:80]}"
            logger.info("WA msg from %s (from_me=%s id=%s): %s", sender_jid, from_me, message_id, text[:200])

            # DPV-006: forward a Django
            payload = {
                "event_type": "message",
                "from_me": from_me,
                "jid": sender_jid,
                "message_id": message_id,
                "text": text,
                "timestamp": timestamp,
            }
            asyncio.create_task(self._forward_to_django(payload))

        @self._client.event(PairStatusEv)
        async def on_pair(_, ev):
            logger.info("Pair status: %r", ev)

    async def start(self):
        from neonize.aioze.client import NewAClient

        Path(self.session_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            # El cliente se instancia con la ruta del SQLite de sesión.
            self._client = NewAClient(self.session_path)
            self._register_handlers()

            # neonize 0.3.16: connect() no acepta qr_callback; el QR viene via QREv.
            self._connect_task = asyncio.create_task(self._client.connect())
            logger.info("WA client task started (session=%s)", self.session_path)
        except Exception as e:
            self._last_error = f"start_failed: {str(e)[:300]}"
            logger.exception("Failed to start WA client: %s", e)

    async def stop(self):
        if self._client:
            try:
                await self._client.disconnect()
            except Exception as e:
                logger.warning("disconnect error: %s", e)
        if self._connect_task:
            self._connect_task.cancel()
            try:
                await self._connect_task
            except (asyncio.CancelledError, Exception):
                pass

    def status(self) -> dict:
        return {
            "connected": self._is_connected,
            "messages_received": self._messages_received,
            "last_message_preview": self._last_message_preview,
            "has_qr": self._qr_data is not None,
            "session_path": self.session_path,
            "last_error": self._last_error,
        }

    async def send_text(self, jid: str, text: str):
        if not self._is_connected or not self._client:
            raise RuntimeError("WA client not connected")
        # La API neonize para send varía: algunas versiones piden JID como objeto,
        # otras como string. Intentamos string primero.
        try:
            await self._client.send_message(jid, text)
        except TypeError:
            # Fallback: algunas versiones requieren un objeto JID
            from neonize.utils import build_jid
            jid_obj = build_jid(jid.split("@")[0])
            await self._client.send_message(jid_obj, text)

    def get_qr_data(self) -> Optional[str]:
        return self._qr_data

    async def _forward_to_django(self, payload: dict):
        """DPV-006: POST del evento 'message' al webhook Django con retries."""
        s = get_settings()
        url = (s.django_webhook_url or "").strip()
        if not url:
            logger.debug("django_webhook_url vacío; forward omitido")
            return
        headers = {}
        if s.django_webhook_token:
            headers["X-Auth-Token"] = s.django_webhook_token
        max_retries = max(0, int(s.django_webhook_max_retries))
        timeout = int(s.django_webhook_timeout_seconds)
        backoff = 1.0
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                if 200 <= resp.status_code < 300:
                    logger.info("forward OK (attempt=%d) status=%s", attempt + 1, resp.status_code)
                    return
                logger.warning(
                    "forward no-OK attempt=%d status=%s body=%s",
                    attempt + 1, resp.status_code, resp.text[:300],
                )
            except Exception as exc:
                logger.warning("forward exception attempt=%d: %s", attempt + 1, exc)
            if attempt < max_retries:
                await asyncio.sleep(backoff)
                backoff *= 2
        logger.error("forward a Django falló tras %d intentos", max_retries + 1)
