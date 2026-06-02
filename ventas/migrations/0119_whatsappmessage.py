import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """WhatsApp Cloud API: tabla WhatsAppMessage (persistencia de conversaciones).
    Tabla NUEVA -> segura de desplegar; correr `migrate` MANUAL en Render."""

    dependencies = [
        ('ventas', '0118_conexion_masajes_ficha_bienestar'),
    ]

    operations = [
        migrations.CreateModel(
            name='WhatsAppMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('direction', models.CharField(choices=[('in', 'Entrante'), ('out', 'Saliente')], db_index=True, max_length=3)),
                ('wa_message_id', models.CharField(db_index=True, help_text='ID del mensaje en Meta (idempotencia).', max_length=128, unique=True)),
                ('phone', models.CharField(db_index=True, help_text='Teléfono E.164 del cliente.', max_length=20)),
                ('body', models.TextField(blank=True)),
                ('msg_type', models.CharField(default='text', help_text='text, image, audio, etc.', max_length=30)),
                ('timestamp', models.DateTimeField(db_index=True, help_text='Momento del mensaje (de Meta).')),
                ('status', models.CharField(blank=True, choices=[('sent', 'Enviado'), ('delivered', 'Entregado'), ('read', 'Leído'), ('received', 'Recibido'), ('failed', 'Error')], max_length=12)),
                ('contact_name', models.CharField(blank=True, max_length=160)),
                ('requiere_atencion', models.BooleanField(db_index=True, default=False, help_text='Entrante sin atender por el operador.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('cliente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='whatsapp_messages', to='ventas.cliente')),
                ('contacto_whatsapp', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mensajes_wa', to='ventas.contactowhatsapp')),
            ],
            options={
                'verbose_name': 'Mensaje WhatsApp',
                'verbose_name_plural': 'Mensajes WhatsApp',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='whatsappmessage',
            index=models.Index(fields=['phone', 'timestamp'], name='idx_wamsg_phone_ts'),
        ),
    ]
