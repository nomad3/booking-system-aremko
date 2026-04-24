from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("destino_puerto_varas", "0006_add_telegram_channel_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentPromptTemplate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        help_text="Identificador interno estable. Ej: 'dpv-main-guide'. No cambiar en caliente.",
                        max_length=80,
                        unique=True,
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Nombre descriptivo para el admin. Ej: 'Destino Puerto Varas · Guía principal'.",
                        max_length=150,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Solo el template activo con el slug buscado será utilizado.",
                    ),
                ),
                (
                    "system_prompt",
                    models.TextField(
                        help_text=(
                            "Prompt de sistema del agente. Puede incluir instrucciones, tono, reglas, "
                            "políticas de derivación a Aremko, etc. Los lugares/circuitos los inyecta el "
                            "agent_service vía tools — NO los hardcodees aquí."
                        )
                    ),
                ),
                (
                    "model_name",
                    models.CharField(
                        default="anthropic/claude-3.5-sonnet",
                        help_text="Identificador del modelo en OpenRouter. Ej: 'anthropic/claude-3.5-sonnet', 'openai/gpt-4o-mini'.",
                        max_length=120,
                    ),
                ),
                (
                    "temperature",
                    models.DecimalField(
                        decimal_places=2,
                        default=0.7,
                        help_text="0.0 (muy predecible) a 1.0+ (más creativo). 0.5-0.8 recomendado para conversaciones.",
                        max_digits=3,
                    ),
                ),
                (
                    "max_output_tokens",
                    models.PositiveIntegerField(
                        default=600,
                        help_text="Tope de tokens de salida por respuesta. WhatsApp/Telegram = respuestas cortas.",
                    ),
                ),
                (
                    "history_window",
                    models.PositiveSmallIntegerField(
                        default=10,
                        help_text="Cuántos mensajes previos de la conversación enviar al LLM como contexto.",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        help_text="Notas internas sobre este template (ej: changelog, A/B test en curso).",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Template de prompt del agente",
                "verbose_name_plural": "Templates de prompt del agente",
                "ordering": ["slug"],
            },
        ),
    ]
