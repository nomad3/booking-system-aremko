# Generated manually for GiftCard AI personalization feature

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0059_add_tramos_validos'),
    ]

    operations = [
        # 1. Extender choices de estado
        migrations.AlterField(
            model_name='giftcard',
            name='estado',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('por_cobrar', 'Por Cobrar'),
                    ('cobrado', 'Cobrado'),
                    ('activo', 'Activo'),
                    ('canjeado', 'Canjeado'),
                    ('expirado', 'Expirado'),
                ],
                default='activo'
            ),
        ),

        # 2. Datos del comprador
        migrations.AddField(
            model_name='giftcard',
            name='comprador_nombre',
            field=models.CharField(max_length=255, blank=True, verbose_name='Nombre del comprador'),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='comprador_email',
            field=models.EmailField(blank=True, verbose_name='Email del comprador'),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='comprador_telefono',
            field=models.CharField(max_length=20, blank=True, verbose_name='Teléfono del comprador'),
        ),

        # 3. Datos del destinatario para personalización IA
        migrations.AddField(
            model_name='giftcard',
            name='destinatario_nombre',
            field=models.CharField(max_length=100, blank=True, verbose_name='Nombre/Apodo del destinatario'),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='destinatario_email',
            field=models.EmailField(blank=True, verbose_name='Email del destinatario'),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='destinatario_telefono',
            field=models.CharField(max_length=20, blank=True, verbose_name='Teléfono del destinatario'),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='destinatario_relacion',
            field=models.CharField(max_length=100, blank=True, verbose_name='Relación con el comprador'),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='detalle_especial',
            field=models.TextField(blank=True, verbose_name='Detalle especial para IA'),
        ),

        # 4. Configuración de mensaje IA
        migrations.AddField(
            model_name='giftcard',
            name='tipo_mensaje',
            field=models.CharField(
                max_length=50,
                choices=[
                    ('romantico', 'Romántico'),
                    ('cumpleanos', 'Cumpleaños'),
                    ('aniversario', 'Aniversario'),
                    ('celebracion', 'Celebración'),
                    ('relajacion', 'Relajación y Bienestar'),
                    ('parejas', 'Parejas'),
                    ('agradecimiento', 'Agradecimiento'),
                    ('amistad', 'Amistad'),
                ],
                blank=True,
                verbose_name='Tipo de mensaje'
            ),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='mensaje_personalizado',
            field=models.TextField(blank=True, verbose_name='Mensaje personalizado generado por IA'),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='mensaje_alternativas',
            field=models.JSONField(
                default=list,
                blank=True,
                verbose_name='Mensajes alternativos generados',
                help_text='Lista de mensajes generados por IA que el usuario puede elegir'
            ),
        ),

        # 5. Servicio asociado
        migrations.AddField(
            model_name='giftcard',
            name='servicio_asociado',
            field=models.CharField(
                max_length=50,
                choices=[
                    ('tinas', 'Tinas Calientes'),
                    ('masajes', 'Masajes'),
                    ('cabanas', 'Alojamiento en Cabaña'),
                    ('ritual_rio', 'Ritual del Río'),
                    ('celebracion', 'Celebración Especial'),
                    ('monto_libre', 'Monto Libre'),
                ],
                blank=True,
                verbose_name='Servicio/Experiencia'
            ),
        ),

        # 6. PDF y envío
        migrations.AddField(
            model_name='giftcard',
            name='pdf_generado',
            field=models.FileField(
                upload_to='giftcards/pdfs/',
                blank=True,
                null=True,
                verbose_name='PDF de la GiftCard'
            ),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='enviado_email',
            field=models.BooleanField(default=False, verbose_name='Enviado por email'),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='enviado_whatsapp',
            field=models.BooleanField(default=False, verbose_name='Enviado por WhatsApp'),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='fecha_envio',
            field=models.DateTimeField(null=True, blank=True, verbose_name='Fecha de envío'),
        ),

        # 7. Tracking de canje
        migrations.AddField(
            model_name='giftcard',
            name='fecha_canje',
            field=models.DateTimeField(null=True, blank=True, verbose_name='Fecha de canje'),
        ),
        migrations.AddField(
            model_name='giftcard',
            name='reserva_asociada',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='ventas.ventareserva',
                verbose_name='Reserva donde se canjeó'
            ),
        ),
    ]
