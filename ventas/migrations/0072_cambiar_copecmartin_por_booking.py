# Generated manually on 2025-12-26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0071_sistema_pagos_masajistas'),
    ]

    operations = [
        migrations.AlterField(
            model_name='compra',
            name='metodo_pago',
            field=models.CharField(
                max_length=50,
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
                ]
            ),
        ),
        migrations.AlterField(
            model_name='pago',
            name='metodo_pago',
            field=models.CharField(
                max_length=100,
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
                ]
            ),
        ),
    ]
