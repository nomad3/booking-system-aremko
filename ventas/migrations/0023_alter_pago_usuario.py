# Generated by Django 4.2 on 2024-11-17 01:49

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ventas', '0022_alter_pago_usuario'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pago',
            name='usuario',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pagos', to=settings.AUTH_USER_MODEL),
        ),
    ]
