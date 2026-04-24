"""Diagnóstico de configuración del bot Telegram (DPV-007).

Uso en Render Shell:
    python manage.py check_telegram_config

Reporta el estado de las env vars de Telegram sin exponer los valores
sensibles. Además hace una llamada a getMe contra la Bot API para confirmar
que el token realmente autentica.
"""

from __future__ import annotations

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand


def _mask(value: str) -> str:
    if not value:
        return "<vacío>"
    n = len(value)
    if n <= 8:
        return f"len={n} (demasiado corto para mostrar)"
    return f"len={n} prefix={value[:4]}… suffix=…{value[-4:]}"


class Command(BaseCommand):
    help = "Reporta el estado de las env vars de Telegram y valida el token vía getMe."

    def handle(self, *args, **options):
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
        base = getattr(settings, "TELEGRAM_API_BASE_URL", "https://api.telegram.org")
        timeout = int(getattr(settings, "TELEGRAM_SEND_TIMEOUT_SECONDS", 15))
        bot_enabled = getattr(settings, "DPV_BOT_ENABLED", False)
        whitelist = getattr(settings, "DPV_BOT_ENABLED_TELEGRAM_CHAT_IDS", []) or []

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Config DPV Telegram"))
        self.stdout.write(f"  DPV_BOT_ENABLED ................ {bot_enabled}")
        self.stdout.write(f"  TELEGRAM_BOT_TOKEN ............. {_mask(token)}")
        self.stdout.write(f"  TELEGRAM_WEBHOOK_SECRET ........ {_mask(secret)}")
        self.stdout.write(f"  TELEGRAM_API_BASE_URL .......... {base}")
        self.stdout.write(f"  TELEGRAM_SEND_TIMEOUT_SECONDS .. {timeout}")
        self.stdout.write(
            f"  DPV_BOT_ENABLED_TELEGRAM_CHAT_IDS .. {whitelist or '[] (abierto a cualquier chat)'}"
        )

        if not token:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR(
                "TELEGRAM_BOT_TOKEN está vacío → el bot NO puede enviar respuestas."
            ))
            self.stdout.write(
                "Revisar en Render Dashboard → Environment → TELEGRAM_BOT_TOKEN."
            )
            return

        url = f"{base.rstrip('/')}/bot{token}/getMe"
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Validando token vía getMe"))
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url)
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Error de red: {exc}"))
            return

        self.stdout.write(f"  HTTP {resp.status_code}")
        try:
            data = resp.json()
        except Exception:
            self.stdout.write(self.style.ERROR("Respuesta no-JSON; revisar TELEGRAM_API_BASE_URL."))
            self.stdout.write(f"  body: {resp.text[:200]}")
            return

        if not data.get("ok"):
            self.stdout.write(self.style.ERROR("Token rechazado por Telegram:"))
            self.stdout.write(f"  {data}")
            return

        me = data.get("result") or {}
        self.stdout.write(self.style.SUCCESS("Token válido. Bot:"))
        self.stdout.write(f"  id ........ {me.get('id')}")
        self.stdout.write(f"  username .. @{me.get('username')}")
        self.stdout.write(f"  name ...... {me.get('first_name')}")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            "Si este comando imprime esto pero el bot no responde en Telegram,"
        ))
        self.stdout.write(self.style.SUCCESS(
            "revisar logs de Render buscando 'Telegram sendMessage' para ver el error real."
        ))
