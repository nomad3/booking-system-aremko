"""Migración inicial de la bandeja omnicanal (H-016).

App AISLADA drift-safe: SOLO crea la tabla `inbox_omnicanal_channelmessage`. Sin
dependencias con `ventas` (el vínculo a Cliente se guarda como id plano, no FK), así
que es puramente aditiva y no dispara nada del drift AR-034.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ChannelMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('canal', models.CharField(choices=[('whatsapp', 'WhatsApp'), ('instagram', 'Instagram')], db_index=True, max_length=20)),
                ('external_id', models.CharField(db_index=True, help_text='Identidad de la conversación en el canal (IG: IGSID; WA: teléfono).', max_length=120)),
                ('external_message_id', models.CharField(help_text='ID del mensaje en el canal (idempotencia). IG: mid.', max_length=190, unique=True)),
                ('direction', models.CharField(choices=[('in', 'Entrante'), ('out', 'Saliente')], db_index=True, max_length=3)),
                ('body', models.TextField(blank=True)),
                ('msg_type', models.CharField(default='text', help_text='text, image, story, share, etc.', max_length=30)),
                ('timestamp', models.DateTimeField(db_index=True, help_text='Momento del mensaje (del canal).')),
                ('status', models.CharField(blank=True, max_length=12)),
                ('contact_name', models.CharField(blank=True, help_text='@username o nombre resuelto por aremko-cli.', max_length=200)),
                ('cliente_id', models.PositiveIntegerField(blank=True, db_index=True, null=True)),
                ('requiere_atencion', models.BooleanField(default=False, db_index=True, help_text='Entrante sin atender por el operador.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Mensaje omnicanal',
                'verbose_name_plural': 'Mensajes omnicanal',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='channelmessage',
            index=models.Index(fields=['canal', 'external_id', 'timestamp'], name='idx_chmsg_conv_ts'),
        ),
        migrations.AddIndex(
            model_name='channelmessage',
            index=models.Index(fields=['canal', 'requiere_atencion'], name='idx_chmsg_canal_req'),
        ),
    ]
