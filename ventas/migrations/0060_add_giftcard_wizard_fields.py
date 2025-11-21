# Generated manually on 2025-11-17
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0059_add_tramos_validos'),
    ]

    operations = [
        # Datos del comprador (ahora capturados en checkout en vez de wizard)
        migrations.AddField(
            model_name='giftcard',
            name='comprador_nombre',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='comprador_email',
            field=models.EmailField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='comprador_telefono',
            field=models.CharField(max_length=20, null=True, blank=True),
        ),

        # Datos del destinatario (para mensajes personalizados)
        migrations.AddField(
            model_name='giftcard',
            name='destinatario_nombre',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='destinatario_email',
            field=models.EmailField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='destinatario_telefono',
            field=models.CharField(max_length=20, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='destinatario_relacion',
            field=models.CharField(max_length=100, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='detalle_especial',
            field=models.TextField(null=True, blank=True),
        ),

        # Configuración de mensaje IA
        migrations.AddField(
            model_name='giftcard',
            name='tipo_mensaje',
            field=models.CharField(max_length=50, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='mensaje_personalizado',
            field=models.TextField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='mensaje_alternativas',
            field=models.JSONField(default=list, null=True, blank=True),
        ),

        # Servicio asociado
        migrations.AddField(
            model_name='giftcard',
            name='servicio_asociado',
            field=models.CharField(max_length=100, null=True, blank=True),
        ),
    ]
