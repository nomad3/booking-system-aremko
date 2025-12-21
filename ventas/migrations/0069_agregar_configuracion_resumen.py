# Generated manually for ConfiguracionResumen and Servicio.informacion_adicional

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0068_servicio_visible_en_matriz'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracionResumen',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('encabezado', models.TextField(default='Confirma tu Reserva en Aremko Spa', help_text='Título principal del resumen de reserva', verbose_name='Encabezado')),
                ('datos_transferencia', models.TextField(default='Para confirmación reserva abonar 100% a:\n\nAremko Hotel Spa Rut 76.485.192-7\nMercado Pago Cta Vista 1016006859\n\nPara confirmar su reserva nos debe llegar un correo de la entidad pagadora al realizar la transferencia ingrese el correo ventas@aremko.cl, indicando NRO Reserva y fecha de esta reserva.\n\nLa reserva se considerará confirmada únicamente una vez recibido el comprobante en el correo y también despachar imagen por este medio donde se especifica claramente detalles de la transferencia.', help_text='Información completa para pago por transferencia bancaria', verbose_name='Datos de Transferencia')),
                ('link_pago_mercadopago', models.URLField(default='https://link.mercadopago.cl/aremko', help_text='URL para pago con tarjeta a través de Mercado Pago', verbose_name='Link Mercado Pago')),
                ('texto_link_pago', models.TextField(default='Ingresa al link, elige cómo pagar, ¡y listo!', help_text='Texto que acompaña al link de Mercado Pago', verbose_name='Texto Link de Pago')),
                ('tina_yate_texto', models.TextField(default='Tina Yate agua fría (sin costo adicional)\nTemperatura garantizada menos de 37°grados su tina es gratis\nNo incluye toallas o batas.', help_text='Texto sobre tina yate y garantía de temperatura (se muestra cuando hay tinas)', verbose_name='Texto Tina Yate')),
                ('sauna_no_disponible', models.TextField(default='(Reserva no incluye sauna por que este no está disponible)', help_text='Aclaración sobre sauna (se muestra cuando hay alojamiento)', verbose_name='Texto Sauna No Disponible')),
                ('politica_alojamiento', models.TextField(default='Alojamiento : Si nos avisa con más de 48hrs de anticipación antes de que inicie su reserva (16:00 hrs Check in), se puede pedir reembolso total o cambio de fecha sin penalidad. Si no se avisa con menos de 48hrs antes de su reserva, lamentablemente la has perdido.', help_text='Política de cancelación para servicios de alojamiento', verbose_name='Política Alojamiento')),
                ('politica_tinas_masajes', models.TextField(default='Tina / Masajes : Si nos avisa con más de 24hrs de anticipación antes de que inicie su reserva, se puede pedir reembolso total o cambio de fecha sin penalidad. Si no se avisa con menos de 24hrs antes de su reserva, lamentablemente la has perdido.', help_text='Política de cancelación para tinas y masajes', verbose_name='Política Tinas/Masajes')),
                ('equipamiento_cabanas', models.TextField(default='Cabaña equipada:*\nNuestras cabañas cuentan con todas las comodidades para que disfrutes al máximo: mini refrigerador, microondas, lavaplatos, tostadora, hervidor, loza, aire acondicionado, wifi y secador de pelo.', help_text='Descripción del equipamiento general de las cabañas', verbose_name='Equipamiento Cabañas')),
                ('cortesias_alojamiento', models.TextField(default='Detalle especial:\nTe ofrecemos cortesías como té negro, infusiones especiales y té Twinings para endulzar naturalmente tus momentos de relax.', help_text='Cortesías incluidas en el alojamiento', verbose_name='Cortesías Alojamiento')),
                ('seguridad_pasarela', models.TextField(default='Pasarela:\nPor tu seguridad, al transitar por las pasarelas, te pedimos usar zapatos cómodos y antideslizantes. El uso de pasamanos es obligatorio y las sandalias no están permitidas.', help_text='Recomendaciones de seguridad para pasarelas', verbose_name='Seguridad Pasarela')),
                ('cortesias_generales', models.TextField(default='Cortesías: Durante tu estadía encontrarás en recepción un espacio de autoservicio de té e infusiones.', help_text='Cortesías disponibles para servicios de tinas/masajes', verbose_name='Cortesías Generales')),
                ('despedida', models.TextField(default='Estamos aquí para asegurarnos de que tengas una experiencia inolvidable. Si tienes dudas o necesitas algo más, no dudes en escribirnos.\n\nGracias por elegir Aremko Spa para tu relax.', help_text='Texto de despedida al final del resumen', verbose_name='Despedida')),
            ],
            options={
                'verbose_name': 'Configuración de Resumen de Reserva',
                'verbose_name_plural': 'Configuración de Resumen de Reserva',
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='servicio',
            name='informacion_adicional',
            field=models.TextField(blank=True, help_text='Información específica del servicio que se incluirá en el resumen de reserva (ej: equipamiento de cabaña, características especiales).', verbose_name='Información Adicional para Resumen'),
        ),
    ]
