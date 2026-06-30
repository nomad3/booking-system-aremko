# Migración inicial de conciliación bancaria (AP-001 · Tier-2 AgentProvision)

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('ventas', '0126_ritualrio_publicacion'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReconciliacionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('referencia', models.CharField(db_index=True, help_text='ID único del movimiento (operación MP, hash de transferencia, etc.). Clave de idempotencia: el mismo movimiento no se aplica dos veces.', max_length=255, unique=True)),
                ('monto', models.DecimalField(decimal_places=0, help_text='Monto aplicado (snapshot, por si el Pago se borra).', max_digits=10)),
                ('metodo_pago', models.CharField(help_text='Método con que se registró el Pago (ej. transferencia, mercadopago).', max_length=100)),
                ('origen', models.CharField(default='gmail', help_text='De dónde leyó AgentProvision el movimiento (gmail, mercadopago, manual…).', max_length=50)),
                ('actor', models.CharField(default='agentprovision', help_text='Quién aplicó la conciliación (agente o usuario).', max_length=100)),
                ('fecha_movimiento', models.DateTimeField(blank=True, help_text='Fecha real del movimiento bancario (de la fuente), distinta de creado_en.', null=True)),
                ('payload', models.JSONField(blank=True, default=dict, help_text='Datos crudos del movimiento que mandó AgentProvision (auditoría).')),
                ('estado', models.CharField(choices=[('aplicado', 'Aplicado'), ('reversado', 'Reversado')], db_index=True, default='aplicado', max_length=20)),
                ('notas', models.TextField(blank=True, default='')),
                ('creado_en', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('pago', models.ForeignKey(blank=True, help_text='Pago creado al aplicar la conciliación.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reconciliaciones', to='ventas.pago')),
                ('reserva', models.ForeignKey(blank=True, help_text='Reserva a la que se aplicó el pago (SET_NULL para preservar el log).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reconciliaciones', to='ventas.ventareserva')),
            ],
            options={
                'verbose_name': 'Log de conciliación',
                'verbose_name_plural': 'Logs de conciliación',
                'db_table': 'conciliacion_reconciliacionlog',
                'ordering': ['-creado_en'],
            },
        ),
        migrations.AddIndex(
            model_name='reconciliacionlog',
            index=models.Index(fields=['origen'], name='recon_origen_idx'),
        ),
    ]
