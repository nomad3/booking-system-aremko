from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("destino_puerto_varas", "0004_add_llm_metadata_to_message"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversationmessage",
            name="external_message_id",
            field=models.CharField(
                max_length=120, blank=True, default="", db_index=True
            ),
        ),
    ]
