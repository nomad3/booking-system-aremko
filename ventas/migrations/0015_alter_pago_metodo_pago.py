# Generated by Django 4.2 on 2024-10-23 15:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0014_alter_reservaproducto_venta_reserva'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pago',
            name='metodo_pago',
            field=models.CharField(choices=[('tarjeta', 'Tarjeta de Crédito/Débito'), ('efectivo', 'Efectivo'), ('webpay', 'WebPay'), ('descuento', 'Descuento'), ('giftcard', 'GiftCard'), ('flow', 'FLOW'), ('mercadopago', 'MercadoPago'), ('scotiabank', 'Tranferencia ScotiaBank'), ('bancoestado', 'Transferencia BancoEstado'), ('cuentarut', 'Transferencia CuentaRut'), ('machjorge', 'mach jorge'), ('machalda', 'mach alda'), ('bcialda', 'bci alda'), ('andesalda', 'andes alda'), ('mercadopagoaremko', 'mercadopago aremko'), ('scotiabankalda', 'scotiabank alda')], max_length=100),
        ),
    ]
