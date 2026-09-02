# Escrita a mano: `makemigrations` se queda esperando una respuesta interactiva
# por un cambio pendiente de OTRA app (el drift conocido), y contestarla habría
# metido ese cambio ajeno en esta migración. Acá solo se crea la tabla nueva.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ventas', '0137_renombra_medio_transferencia_mp'),
        ('facturacion', '0003_mediopago_visible_al_cobrar'),
    ]

    operations = [
        migrations.CreateModel(
            name='DecisionSinBoleta',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('motivo', models.CharField(
                    blank=True, default='',
                    help_text='Opcional: por qué no se emitió (ej. «el cliente ya tiene su voucher»).',
                    max_length=200)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('pago', models.OneToOneField(
                    help_text='El pago que se decidió no boletear.',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='decision_sin_boleta', to='ventas.pago')),
                ('usuario', models.ForeignKey(
                    blank=True, help_text='Quién lo decidió.', null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Pago sin boleta (decidido)',
                'verbose_name_plural': 'Pagos sin boleta (decididos)',
                'ordering': ['-creado_en'],
            },
        ),
    ]
