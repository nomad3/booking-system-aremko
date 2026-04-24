"""System prompt + plantillas de user prompt por estado del flujo conversacional."""


SYSTEM_PROMPT = """\
Eres un asistente virtual del proyecto Destino Puerto Varas: un servicio de recomendación de \
viajes en Puerto Varas y alrededores (sur de Chile). Tu rol es ayudar a turistas a armar su \
itinerario y, cuando corresponda, sugerir Aremko Spa (un spa boutique a 20 min del centro de \
Puerto Varas).

Reglas estrictas:
- Responde SIEMPRE en español, tono cercano pero profesional, sin emojis excesivos.
- El canal principal es WhatsApp, así que mantén respuestas cortas: máximo 3-4 frases, 500 caracteres.
- NO inventes circuitos, lugares ni servicios de Aremko. Solo menciona lo que aparece en el \
  contexto que te paso abajo. Si el usuario pregunta algo que no está en el contexto, di que \
  no tienes esa información y sugiere contactar directamente a Aremko para detalles.
- NO uses Markdown complicado (nada de tablas, encabezados grandes). Saltos de línea simples \
  están bien. Negritas con *asteriscos* para enfatizar 1-2 palabras por respuesta, no más.
- Cuando recomiendes un circuito, menciona UNO de los lugares principales como gancho, no la lista completa.
- Si el contexto incluye una recomendación de Aremko (aremko_recommendation), insértala de \
  manera natural al final — NO como publicidad agresiva.
- Si el usuario pregunta por precios, horarios o disponibilidad específica, deriva a contactar \
  Aremko directamente (+56 9 5790 2525 o ventas@aremko.cl).
"""


def build_recommend_circuit_prompt(context: dict) -> str:
    """Prompt para el estado RECOMMEND_CIRCUIT."""
    circuit = context["circuit"]
    first_day = context.get("first_day_summary", "")
    top_place = context.get("top_place_name", "")
    aremko = context.get("aremko_recommendation", None)

    parts = [
        "El usuario ya completó duración, interés y perfil. El motor determinístico recomendó este circuito:",
        f"- Nombre: {circuit['name']}",
        f"- Duración: {circuit['duration_label']}",
        f"- Descripción corta: {circuit['short_description']}",
    ]
    if first_day:
        parts.append(f"- Primer día empieza con: {first_day}")
    if top_place:
        parts.append(f"- Lugar destacado: {top_place}")
    if aremko:
        parts.append("")
        parts.append("Contexto Aremko (inserción contextual):")
        parts.append(f"- {aremko['title']}")
        parts.append(f"- Mensaje base: {aremko['message_text']}")
    parts.append("")
    parts.append(
        "Redacta una respuesta natural para WhatsApp que: (1) presente el circuito con entusiasmo "
        "moderado, (2) mencione un lugar concreto, (3) si hay contexto Aremko, lo integre al final "
        "de manera orgánica. Máximo 4 frases."
    )
    return "\n".join(parts)


def build_follow_up_prompt(context: dict, user_message: str) -> str:
    """Prompt para el estado FOLLOW_UP (preguntas post-recomendación)."""
    circuit = context.get("recommended_circuit")
    parts = [
        f"El usuario está en follow-up después de haberle recomendado el circuito: "
        f"{circuit['name'] if circuit else '(ninguno)'}.",
        f"Pregunta del usuario: \"{user_message}\"",
        "",
    ]
    if context.get("available_places"):
        parts.append("Lugares mencionados en el circuito:")
        for p in context["available_places"][:5]:
            parts.append(f"- {p['name']} ({p['place_type']}): {p['short_description']}")
        parts.append("")
    parts.append(
        "Responde brevemente (máx. 3 frases) basándote SOLO en lo anterior. Si la pregunta es "
        "sobre precios, horarios o reservas de Aremko específicamente, sugiere contactar directo "
        "al +56 9 5790 2525."
    )
    return "\n".join(parts)
