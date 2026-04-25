"""DPV CMS-IA · Capa 3: narrativa editorial de Circuits generada por IA.

Añade a Circuit:
  - places_signature (CharField): hash de paradas para detectar staleness.
  - last_narrative_at (DateTimeField): cuándo se aplicó la última narrativa.

Crea CircuitNarrativeDraft (FK Circuit, status, places_signature, proposed_data,
métricas LLM, review_notes, reviewed_by/at, applied_at).

Migración escrita a mano (drift-safe) — sólo destino_puerto_varas.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("destino_puerto_varas", "0009_place_enrichment_schema"),
    ]

    operations = [
        migrations.AddField(
            model_name="circuit",
            name="places_signature",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Hash de las paradas en orden, calculado al generar la narrativa. "
                    "Si difiere del hash actual, la narrativa quedó stale y conviene regenerarla."
                ),
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="circuit",
            name="last_narrative_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Última vez que se aplicó una narrativa IA al long_description.",
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="CircuitNarrativeDraft",
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
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Borrador (pendiente revisión)"),
                            ("approved", "Aprobado (listo para aplicar)"),
                            ("rejected", "Rechazado"),
                            ("applied", "Aplicado al Circuit"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "places_signature",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Hash de paradas en el momento de generar (para auditar staleness).",
                        max_length=64,
                    ),
                ),
                (
                    "proposed_data",
                    models.JSONField(
                        default=dict,
                        help_text=(
                            "Estructura: {'circuit_long_description': '...', "
                            "'day_summaries': {'1': '...', '2': '...'}}"
                        ),
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
                    "circuit",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="narrative_drafts",
                        to="destino_puerto_varas.circuit",
                    ),
                ),
            ],
            options={
                "verbose_name": "Borrador de narrativa",
                "verbose_name_plural": "Borradores de narrativa",
                "ordering": ["-created_at"],
            },
        ),
    ]
