# Generada a mano: `makemigrations` se colgó en el contenedor y, además, así
# queda a la vista que este cambio NO toca la base — solo la etiqueta que ve
# quien cobra. «mercadopago aremko» pasa a llamarse «Transferencia a Mercado
# Pago», que es lo que de verdad es (Jorge, 02-09-2026).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0136_foto_desayuno_landing_dia'),
    ]

    operations = [
        migrations.AlterField(
            model_name='compra',
            name='metodo_pago',
            field=models.CharField(choices=[('tarjeta', 'Tarjeta de Crédito/Débito'), ('efectivo', 'Efectivo'), ('transferencia', 'Transferencia Bancaria'), ('webpay', 'WebPay'), ('descuento', 'Descuento'), ('giftcard', 'GiftCard'), ('flow', 'FLOW'), ('mercadopago', 'MercadoPago'), ('mercadopago_link', 'Mercado Pago Link'), ('scotiabank', 'Transferencia ScotiaBank'), ('bancoestado', 'Transferencia BancoEstado'), ('cuentarut', 'Transferencia CuentaRut'), ('machjorge', 'mach jorge'), ('machalda', 'mach alda'), ('bicegoalda', 'bicego alda'), ('bcialda', 'bci alda'), ('andesalda', 'andes alda'), ('mercadopagoaremko', 'Transferencia a Mercado Pago'), ('scotiabankalda', 'scotiabank alda'), ('copecjorge', 'copec jorge'), ('copecalda', 'copec alda'), ('booking', 'booking')], max_length=50),
        ),
        migrations.AlterField(
            model_name='pago',
            name='metodo_pago',
            field=models.CharField(choices=[('tarjeta', 'Tarjeta de Crédito/Débito'), ('efectivo', 'Efectivo'), ('transferencia', 'Transferencia Bancaria'), ('webpay', 'WebPay'), ('descuento', 'Descuento'), ('giftcard', 'GiftCard'), ('flow', 'FLOW'), ('mercadopago', 'MercadoPago'), ('mercadopago_link', 'Mercado Pago Link'), ('scotiabank', 'Transferencia ScotiaBank'), ('bancoestado', 'Transferencia BancoEstado'), ('cuentarut', 'Transferencia CuentaRut'), ('machjorge', 'mach jorge'), ('machalda', 'mach alda'), ('bicegoalda', 'bicego alda'), ('bcialda', 'bci alda'), ('andesalda', 'andes alda'), ('mercadopagoaremko', 'Transferencia a Mercado Pago'), ('scotiabankalda', 'scotiabank alda'), ('copecjorge', 'copec jorge'), ('copecalda', 'copec alda'), ('booking', 'booking')], db_index=True, max_length=100),
        ),
    ]
