"""Aditiva: agrega campos de metadata LLM a ConversationMessage."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("destino_puerto_varas", "0003_seed_puerto_varas_content"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversationmessage",
            name="llm_model",
            field=models.CharField(max_length=80, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="conversationmessage",
            name="llm_input_tokens",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="conversationmessage",
            name="llm_output_tokens",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="conversationmessage",
            name="llm_cost_usd",
            field=models.DecimalField(max_digits=10, decimal_places=6, default=0),
        ),
        migrations.AddField(
            model_name="conversationmessage",
            name="llm_latency_ms",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="conversationmessage",
            name="llm_error",
            field=models.CharField(max_length=200, blank=True, default=""),
        ),
    ]
