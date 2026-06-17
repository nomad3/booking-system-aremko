"""H-023: agregar Facebook Messenger como canal (mirror de H-016 Instagram).

Messenger Platform es el mismo formato que IG: entry[].messaging[]. Identidad por PSID
(Page-Scoped ID del cliente). Página de Aremko = 555157687911449. Canal REACTIVO
(marketing pagado diferido).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inbox_omnicanal', '0002_channelmessage_media'),
    ]

    operations = [
        migrations.AlterField(
            model_name='channelmessage',
            name='canal',
            field=models.CharField(
                choices=[
                    ('whatsapp', 'WhatsApp'),
                    ('instagram', 'Instagram'),
                    ('messenger', 'Facebook Messenger'),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
    ]
