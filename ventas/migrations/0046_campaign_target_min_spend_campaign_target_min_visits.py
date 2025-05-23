# Generated by Django 4.2 on 2025-04-15 00:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0045_homepageconfig_activity_campaign'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='target_min_spend',
            field=models.DecimalField(blank=True, decimal_places=0, default=0, max_digits=10, null=True, verbose_name='Gasto Mínimo Cliente (CLP)'),
        ),
        migrations.AddField(
            model_name='campaign',
            name='target_min_visits',
            field=models.PositiveIntegerField(blank=True, default=0, null=True, verbose_name='Visitas Mínimas Cliente'),
        ),
    ]
