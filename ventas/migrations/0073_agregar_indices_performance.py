# Generated manually on 2025-12-27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0072_cambiar_copecmartin_por_booking'),
    ]

    operations = [
        # Agregar índice a GiftCard.fecha_emision
        migrations.AlterField(
            model_name='giftcard',
            name='fecha_emision',
            field=models.DateField(db_index=True, default=models.functions.Now()),
        ),
        # Agregar índice a GiftCard.estado
        migrations.AlterField(
            model_name='giftcard',
            name='estado',
            field=models.CharField(
                choices=[('por_cobrar', 'Por Cobrar'), ('cobrado', 'Cobrado')],
                db_index=True,
                default='por_cobrar',
                max_length=10
            ),
        ),
        # Agregar índice a Pago.metodo_pago
        migrations.AlterField(
            model_name='pago',
            name='metodo_pago',
            field=models.CharField(
                choices=[
                    ('tarjeta', 'Tarjeta de Crédito/Débito'),
                    ('efectivo', 'Efectivo'),
                    ('transferencia', 'Transferencia Bancaria'),
                    ('webpay', 'WebPay'),
                    ('descuento', 'Descuento'),
                    ('giftcard', 'GiftCard'),
                    ('flow', 'FLOW'),
                    ('mercadopago', 'MercadoPago'),
                    ('mercadopago_link', 'Mercado Pago Link'),
                    ('scotiabank', 'Transferencia ScotiaBank'),
                    ('bancoestado', 'Transferencia BancoEstado'),
                    ('cuentarut', 'Transferencia CuentaRut'),
                    ('machjorge', 'mach jorge'),
                    ('machalda', 'mach alda'),
                    ('bicegoalda', 'bicego alda'),
                    ('bcialda', 'bci alda'),
                    ('andesalda', 'andes alda'),
                    ('mercadopagoaremko', 'mercadopago aremko'),
                    ('scotiabankalda', 'scotiabank alda'),
                    ('copecjorge', 'copec jorge'),
                    ('copecalda', 'copec alda'),
                    ('booking', 'booking'),
                ],
                db_index=True,
                max_length=100
            ),
        ),
        # Agregar índice a GiftCardExperiencia.activo
        migrations.AlterField(
            model_name='giftcardexperiencia',
            name='activo',
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text='Si está inactivo, no aparece en el wizard'
            ),
        ),
    ]
