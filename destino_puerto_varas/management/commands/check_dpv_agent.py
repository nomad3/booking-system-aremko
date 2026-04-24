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

    def add_arguments(self, parser):
        parser.add_argument(
            "--test-call",
            action="store_true",
            help="Además hace una llamada de prueba al LLM con una conversación dummy.",
        )

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
            return

        if not options.get("test_call"):
            self.stdout.write("")
            self.stdout.write(
                "Para probar una llamada real al LLM: python manage.py check_dpv_agent --test-call"
            )
            return

        # Test call: conversación dummy, usuario dice "hola"
        from destino_puerto_varas.enums import ChannelType, ConversationStatus
        from destino_puerto_varas.models import LeadConversation
        from destino_puerto_varas.services.agent_service import respond

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Test call contra el LLM"))
        self.stdout.write("  Creando conversación dummy (canal=WEB, external_id=check_dpv_agent_test)...")

        dummy, _ = LeadConversation.objects.get_or_create(
            channel=ChannelType.WEB,
            external_id="check_dpv_agent_test",
            defaults={
                "status": ConversationStatus.OPEN,
                "contact_name": "Diagnóstico agente",
            },
        )
        # Reset de banderas para no contaminar el test
        dummy.referred_to_aremko = False
        dummy.showed_interest_in_aremko = False
        dummy.status = ConversationStatus.OPEN
        dummy.detected_interest = ""
        dummy.detected_profile = ""
        dummy.detected_duration_case = None
        dummy.recommended_circuit = None
        dummy.save()

        self.stdout.write('  Enviando mensaje: "hola"...')
        result = respond(dummy, "hola")

        self.stdout.write("")
        self.stdout.write(f"  ok ......... {result.get('ok')}")
        self.stdout.write(f"  error ...... {result.get('error', '-')}")
        meta = result.get("metadata") or {}
        self.stdout.write(f"  model ...... {meta.get('model', '-')}")
        self.stdout.write(f"  tokens in .. {meta.get('input_tokens', 0)}")
        self.stdout.write(f"  tokens out . {meta.get('output_tokens', 0)}")
        self.stdout.write(f"  latency .... {meta.get('latency_ms', 0)} ms")
        tool_calls = result.get("tool_calls") or []
        self.stdout.write(f"  tool_calls . {len(tool_calls)}")
        for i, tc in enumerate(tool_calls):
            self.stdout.write(f"    [{i}] {tc.get('name')} args={tc.get('arguments')}")
        text = result.get("text") or ""
        self.stdout.write("")
        self.stdout.write("  Respuesta del LLM:")
        if text:
            self.stdout.write("  " + "─" * 60)
            for line in text.splitlines() or [text]:
                self.stdout.write(f"  {line}")
            self.stdout.write("  " + "─" * 60)
        else:
            self.stdout.write(self.style.ERROR("    (vacía)"))

        if result.get("ok"):
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("✓ El agente respondió correctamente."))
        else:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR(
                "✗ El agente falló. El error arriba indica la causa "
                "(modelo inexistente, rate limit, créditos, etc.)."
            ))
