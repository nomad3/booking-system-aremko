# H-107: singleton del token de Instagram Login (fuente de verdad + auto-refresh).
# Migración escrita A MANO (drift-safe): makemigrations detecta drift preexistente en
# esta app y pide input interactivo, así que aquí va SOLO el CreateModel nuevo. Los
# help_text calcan los del modelo para que futuros makemigrations no emitan ruido.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inbox_omnicanal', '0003_messenger_channel'),
    ]

    operations = [
        migrations.CreateModel(
            name='InstagramTokenConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.TextField(blank=True, help_text='Token de Instagram Login (larga vida). Pegar aquí el generado en developers.facebook.com; a partir de ahí se refresca solo cada ~7 días.')),
                ('token_actualizado_at', models.DateTimeField(blank=True, help_text='Cuándo se pegó/cambió el token a mano (lo setea el admin). El primer refresh automático espera 7 días desde acá (Meta exige ≥24 h).', null=True)),
                ('expira_estimado', models.DateTimeField(blank=True, help_text='Vencimiento estimado informado por Meta en el último refresh.', null=True)),
                ('ultimo_refresh_at', models.DateTimeField(blank=True, help_text='Último refresh EXITOSO contra Meta.', null=True)),
                ('ultimo_intento_at', models.DateTimeField(blank=True, help_text='Último intento de refresh (exitoso o no); si falla se reintenta cada 6 h.', null=True)),
                ('ultimo_error', models.TextField(blank=True, help_text='Detalle del último refresh fallido (vacío si el último fue OK).')),
                ('ultimo_aviso_at', models.DateTimeField(blank=True, help_text='Último email de alerta enviado (máx 1 al día).', null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Token de Instagram',
                'verbose_name_plural': 'Token de Instagram',
            },
        ),
    ]
