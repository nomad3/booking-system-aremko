"""Diagnóstico del agente conversacional DPV (DPV-008).

Uso en Render Shell:
    python manage.py check_dpv_agent

Reporta el estado de cada precondición de is_agent_available() y opcionalmente
hace un dry-run de una conversación para ver el flujo completo.
"""

from __future__ import annotations

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
    help = "Reporta el estado del agente LLM conversacional (DPV-008)."

    def handle(self, *args, **options):
        from destino_puerto_varas.models import AgentPromptTemplate
        from destino_puerto_varas.services.agent_service import (
            AGENT_SLUG,
            is_agent_available,
        )

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Config del agente DPV"))

        dpv_enabled = getattr(settings, "DPV_LLM_ENABLED", False)
        key = getattr(settings, "OPENROUTER_API_KEY", "")
        model = getattr(settings, "DPV_LLM_MODEL", "")
        base = getattr(settings, "OPENROUTER_BASE_URL", "")

        self.stdout.write(f"  DPV_LLM_ENABLED ......... {dpv_enabled}")
        self.stdout.write(f"  OPENROUTER_API_KEY ...... {_mask(key)}")
        self.stdout.write(f"  OPENROUTER_BASE_URL ..... {base}")
        self.stdout.write(f"  DPV_LLM_MODEL (default) . {model}")

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"Template activo (slug={AGENT_SLUG})"))
        try:
            tpl = AgentPromptTemplate.objects.get(slug=AGENT_SLUG, is_active=True)
        except AgentPromptTemplate.DoesNotExist:
            count_any = AgentPromptTemplate.objects.count()
            self.stdout.write(self.style.ERROR(
                f"  NO existe template activo con slug='{AGENT_SLUG}'."
            ))
            self.stdout.write(f"  Total de templates en DB: {count_any}")
            if count_any == 0:
                self.stdout.write(self.style.WARNING(
                    "  → Probablemente la migración 0008 no se aplicó. "
                    "Correr: python manage.py migrate destino_puerto_varas"
                ))
            return

        self.stdout.write(self.style.SUCCESS(f"  ✓ Template encontrado: {tpl.name}"))
        self.stdout.write(f"    id ................. {tpl.id}")
        self.stdout.write(f"    model_name ......... {tpl.model_name}")
        self.stdout.write(f"    temperature ........ {tpl.temperature}")
        self.stdout.write(f"    max_output_tokens .. {tpl.max_output_tokens}")
        self.stdout.write(f"    history_window ..... {tpl.history_window}")
        self.stdout.write(f"    prompt length ...... {len(tpl.system_prompt)} chars")
        self.stdout.write(f"    updated_at ......... {tpl.updated_at}")

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Resultado is_agent_available()"))
        available = is_agent_available()
        if available:
            self.stdout.write(self.style.SUCCESS("  ✓ True — el agente LLM se usará en la próxima conversación."))
        else:
            self.stdout.write(self.style.ERROR("  ✗ False — el agente NO está disponible; se usará el fallback legacy."))
            if not dpv_enabled:
                self.stdout.write("    Causa: DPV_LLM_ENABLED está en False/vacío.")
            elif not key:
                self.stdout.write("    Causa: OPENROUTER_API_KEY está vacío.")
            else:
                self.stdout.write("    Causa: template activo no encontrado o inactivo.")
