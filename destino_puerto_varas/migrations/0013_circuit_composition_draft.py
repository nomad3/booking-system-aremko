"""DPV CMS-IA · Form 2 (Fase A): composición de Circuit con IA.

Crea CircuitCompositionDraft: borrador donde la IA arma un circuito completo
desde una idea libre del usuario, seleccionando paradas del catálogo de Places
publicados.

Drift-safe: solo CreateModel + FKs a modelos ya existentes (Circuit,
DurationCase). No toca ni el resto del schema ni las apps `ventas` /
`control_gestion`.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("destino_puerto_varas", "0012_place_commercial_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="CircuitCompositionDraft",
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
                    "user_idea",
                    models.TextField(
                        help_text="Descripción libre del circuito que el usuario pidió.",
                    ),
                ),
                (
                    "primary_interest",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("NATURE", "Naturaleza"),
                            ("GASTRONOMY", "Gastronomía"),
                            ("ADVENTURE", "Aventura"),
                            ("RELAX_ROMANTIC", "Relax / Romántico"),
                            ("MIXED", "Mixto"),
                        ],
                        help_text="Interés primario pedido en el form.",
                        max_length=30,
                    ),
                ),
                (
                    "recommended_profile",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("COUPLE", "Pareja"),
                            ("FAMILY", "Familia"),
                            ("FRIENDS", "Amigos"),
                            ("SOLO", "Solo/a"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "anchor_place_ids",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="IDs de Places que el usuario pidió incluir obligatoriamente.",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Borrador (pendiente revisión)"),
                            ("approved", "Aprobado (listo para aplicar)"),
                            ("rejected", "Rechazado"),
                            ("applied", "Aplicado (Circuit creado)"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "proposed_data",
                    models.JSONField(
                        default=dict,
                        help_text="Estructura propuesta por la IA. Ver docstring del modelo.",
                    ),
                ),
                ("llm_model", models.CharField(blank=True, default="", max_length=80)),
                ("llm_input_tokens", models.PositiveIntegerField(default=0)),
                ("llm_output_tokens", models.PositiveIntegerField(default=0)),
                ("llm_latency_ms", models.PositiveIntegerField(default=0)),
                ("review_notes", models.TextField(blank=True)),
                ("reviewed_by", models.CharField(blank=True, max_length=80)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("applied_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "duration_case",
                    models.ForeignKey(
                        blank=True,
                        help_text="Duración pedida en el form. La IA debe respetarla.",
                        null=True,
                        on_delete=models.deletion.PROTECT,
                        related_name="composition_drafts",
                        to="destino_puerto_varas.durationcase",
                    ),
                ),
                (
                    "created_circuit",
                    models.ForeignKey(
                        blank=True,
                        help_text="Circuit que este draft creó al aplicarse.",
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="composition_drafts",
                        to="destino_puerto_varas.circuit",
                    ),
                ),
            ],
            options={
                "verbose_name": "Borrador de circuito (composición IA)",
                "verbose_name_plural": "Borradores de circuito (composición IA)",
                "ordering": ["-created_at"],
            },
        ),
    ]
