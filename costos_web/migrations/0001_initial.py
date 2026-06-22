# -*- coding: utf-8 -*-
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ServicioWeb',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(help_text='Ej: Cloudinary, Render, Claude, OpenRouter.', max_length=120)),
                ('categoria', models.CharField(choices=[('infra', 'Infraestructura / Hosting'), ('ia', 'IA / LLM'), ('email', 'Email / Mensajería'), ('dominio', 'Dominio / DNS'), ('marketing', 'Marketing / Ads'), ('pagos', 'Pagos'), ('otro', 'Otro')], default='otro', max_length=20)),
                ('modalidad', models.CharField(choices=[('suscripcion', 'Suscripción (monto fijo recurrente)'), ('uso', 'Uso / prepago (saldo)')], default='suscripcion', max_length=20)),
                ('activo', models.BooleanField(default=True)),
                ('monto', models.DecimalField(blank=True, decimal_places=2, help_text='Monto del ciclo (suscripción) o de la recarga típica (uso).', max_digits=12, null=True)),
                ('moneda', models.CharField(choices=[('USD', 'USD'), ('CLP', 'CLP'), ('EUR', 'EUR')], default='USD', max_length=3)),
                ('ciclo', models.CharField(choices=[('mensual', 'Mensual'), ('anual', 'Anual'), ('uso', 'Por uso (sin ciclo fijo)'), ('otro', 'Otro')], default='mensual', max_length=10)),
                ('proxima_fecha_pago', models.DateField(blank=True, help_text='Vencimiento / próxima renovación. Lo que ordena el tablero.', null=True)),
                ('ultima_fecha_pago', models.DateField(blank=True, null=True)),
                ('tarjeta_ultimos4', models.CharField(blank=True, default='', help_text='Últimos 4 dígitos. NUNCA el número completo ni el CVV.', max_length=4, validators=[django.core.validators.RegexValidator('^\\d{0,4}$', 'Solo los últimos 4 dígitos.')])),
                ('tarjeta_banco', models.CharField(blank=True, default='', help_text='Ej: Visa Santander, Mastercard.', max_length=80)),
                ('saldo_actual', models.DecimalField(blank=True, decimal_places=2, help_text='Saldo/crédito disponible (servicios de uso).', max_digits=12, null=True)),
                ('saldo_umbral_alerta', models.DecimalField(blank=True, decimal_places=2, help_text='Avisar cuando el saldo baje de este valor.', max_digits=12, null=True)),
                ('saldo_actualizado', models.DateField(blank=True, help_text='Fecha en que se revisó el saldo.', null=True)),
                ('url_facturacion', models.URLField(blank=True, default='', help_text='Panel de facturación del servicio.')),
                ('responsable', models.CharField(blank=True, default='', max_length=80)),
                ('notas', models.TextField(blank=True, default='')),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('actualizado', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Servicio web (costo)',
                'verbose_name_plural': 'Costos de Servicios Web',
                'ordering': ['proxima_fecha_pago', 'nombre'],
            },
        ),
    ]
