# Generated manually for sistema de pagos a masajistas

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ventas', '0070_agregar_configuracion_tips'),
    ]

    operations = [
        # Agregar campos de pago a Proveedor
        migrations.AddField(
            model_name='proveedor',
            name='porcentaje_comision',
            field=models.DecimalField(
                max_digits=5,
                decimal_places=2,
                default=40.00,
                help_text='Porcentaje de comisión del proveedor (ej: 40.00 para 40%)',
                verbose_name='Porcentaje Comisión'
            ),
        ),
        migrations.AddField(
            model_name='proveedor',
            name='es_masajista',
            field=models.BooleanField(
                default=False,
                help_text='Indica si este proveedor es un masajista',
                verbose_name='Es Masajista'
            ),
        ),
        migrations.AddField(
            model_name='proveedor',
            name='rut',
            field=models.CharField(
                max_length=12,
                blank=True,
                null=True,
                help_text='RUT del proveedor para efectos tributarios',
                verbose_name='RUT'
            ),
        ),
        migrations.AddField(
            model_name='proveedor',
            name='banco',
            field=models.CharField(
                max_length=100,
                blank=True,
                null=True,
                help_text='Banco para transferencias',
                verbose_name='Banco'
            ),
        ),
        migrations.AddField(
            model_name='proveedor',
            name='tipo_cuenta',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('corriente', 'Cuenta Corriente'),
                    ('vista', 'Cuenta Vista'),
                    ('ahorro', 'Cuenta de Ahorro'),
                    ('rut', 'Cuenta RUT'),
                ],
                blank=True,
                null=True,
                verbose_name='Tipo de Cuenta'
            ),
        ),
        migrations.AddField(
            model_name='proveedor',
            name='numero_cuenta',
            field=models.CharField(
                max_length=50,
                blank=True,
                null=True,
                help_text='Número de cuenta bancaria',
                verbose_name='Número de Cuenta'
            ),
        ),

        # Crear modelo PagoMasajista
        migrations.CreateModel(
            name='PagoMasajista',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_pago', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Pago')),
                ('periodo_inicio', models.DateField(verbose_name='Periodo Inicio', help_text='Fecha inicio del periodo a pagar')),
                ('periodo_fin', models.DateField(verbose_name='Periodo Fin', help_text='Fecha fin del periodo a pagar')),
                ('monto_bruto', models.DecimalField(max_digits=10, decimal_places=0, verbose_name='Monto Bruto', help_text='Total antes de descuentos')),
                ('porcentaje_retencion', models.DecimalField(max_digits=5, decimal_places=2, default=14.5, verbose_name='% Retención', help_text='Porcentaje de retención de impuestos')),
                ('monto_retencion', models.DecimalField(max_digits=10, decimal_places=0, verbose_name='Monto Retención', help_text='Monto retenido por impuestos')),
                ('monto_neto', models.DecimalField(max_digits=10, decimal_places=0, verbose_name='Monto Neto', help_text='Monto pagado al masajista')),
                ('comprobante', models.ImageField(upload_to='pagos_masajistas/', verbose_name='Comprobante de Transferencia', help_text='Imagen del comprobante bancario')),
                ('numero_transferencia', models.CharField(max_length=100, blank=True, null=True, verbose_name='Número de Transferencia')),
                ('observaciones', models.TextField(blank=True, verbose_name='Observaciones')),
                ('proveedor', models.ForeignKey(on_delete=models.CASCADE, related_name='pagos', to='ventas.proveedor', verbose_name='Masajista')),
                ('creado_por', models.ForeignKey(on_delete=models.SET_NULL, null=True, to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
            ],
            options={
                'verbose_name': 'Pago a Masajista',
                'verbose_name_plural': 'Pagos a Masajistas',
                'ordering': ['-fecha_pago'],
            },
        ),

        # Crear modelo DetalleServicioPago para relacionar servicios con pagos
        migrations.CreateModel(
            name='DetalleServicioPago',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('monto_servicio', models.DecimalField(max_digits=10, decimal_places=0, verbose_name='Monto del Servicio')),
                ('porcentaje_masajista', models.DecimalField(max_digits=5, decimal_places=2, verbose_name='% Comisión', help_text='Porcentaje que se le pagó al masajista')),
                ('monto_masajista', models.DecimalField(max_digits=10, decimal_places=0, verbose_name='Monto para Masajista', help_text='Monto correspondiente al masajista')),
                ('pago', models.ForeignKey(on_delete=models.CASCADE, related_name='detalles', to='ventas.pagomasajista')),
                ('reserva_servicio', models.ForeignKey(on_delete=models.CASCADE, to='ventas.reservaservicio')),
            ],
            options={
                'verbose_name': 'Detalle de Servicio en Pago',
                'verbose_name_plural': 'Detalles de Servicios en Pagos',
            },
        ),

        # Agregar campo para marcar ReservaServicio como pagado al masajista
        migrations.AddField(
            model_name='reservaservicio',
            name='pagado_a_proveedor',
            field=models.BooleanField(
                default=False,
                verbose_name='Pagado al Proveedor',
                help_text='Indica si el servicio ya fue pagado al proveedor/masajista'
            ),
        ),
        migrations.AddField(
            model_name='reservaservicio',
            name='pago_proveedor',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name='servicios_incluidos',
                to='ventas.pagomasajista',
                verbose_name='Pago Asociado',
                help_text='Pago en el que se incluyó este servicio'
            ),
        ),
    ]