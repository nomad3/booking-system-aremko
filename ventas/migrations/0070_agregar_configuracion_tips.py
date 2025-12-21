# Generated manually on 2025-12-21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0069_agregar_configuracion_resumen'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracionTips',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),

                # Encabezado general
                ('encabezado', models.TextField(blank=True, default='Bienvenido a Aremko Spa 🌿', help_text='Título principal de los tips', verbose_name='Encabezado')),
                ('intro', models.TextField(blank=True, default='Gracias por elegirnos para tu estadía. Aquí te compartimos información importante para que disfrutes al máximo tu experiencia:', help_text='Texto introductorio', verbose_name='Introducción')),

                # WiFi Cabañas
                ('wifi_torre', models.CharField(blank=True, default='Red: Torre / Clave: torre2021', max_length=200, verbose_name='WiFi Cabaña Torre')),
                ('wifi_tepa', models.CharField(blank=True, default='Red: TP-Link_3B26 / Clave: 83718748', max_length=200, verbose_name='WiFi Cabaña Tepa')),
                ('wifi_acantilado', models.CharField(blank=True, default='Red: Acantilado / Clave: acantilado', max_length=200, verbose_name='WiFi Cabaña Acantilado')),
                ('wifi_laurel', models.CharField(blank=True, default='Red: Acantilado / Clave: acantilado', max_length=200, verbose_name='WiFi Cabaña Laurel')),
                ('wifi_arrayan', models.CharField(blank=True, default='Red: tp-link_7e8a / Clave: 19146881', max_length=200, verbose_name='WiFi Cabaña Arrayan')),

                # Normas cabañas
                ('norma_mascotas', models.TextField(blank=True, default='❌ Prohibido traer mascotas a Aremko', verbose_name='Norma: Mascotas')),
                ('norma_cocinar', models.TextField(blank=True, default='❌ Prohibido cocinar y realizar asados (interior y exterior de cabañas)', verbose_name='Norma: Cocinar/Asados')),
                ('norma_fumar', models.TextField(blank=True, default='❌ AREMKO ES NO FUMADOR (Ley 20.660)\nFumar en lugares cerrados está prohibido por ley.\nMulta: 2 UTM (~$70.000) + costo de limpieza profunda.\nEl cobro se realiza al momento del check-out.', verbose_name='Norma: No Fumar')),
                ('norma_danos', models.TextField(blank=True, default='⚠️ Multas por daños o limpieza extraordinaria:\nSe aplicarán cargos por daños, artículos faltantes o limpieza inesperada (manchas en sábanas, ropa de cama, toallas).\nLa cabaña será revisada por personal de Aremko al check-out.', verbose_name='Norma: Daños y Limpieza')),

                # Check-out cabañas
                ('checkout_semana', models.TextField(blank=True, default='Domingo a Jueves (antes de 11:00 hrs):\n→ Deja llaves y controles dentro de la cabaña\n→ Asegúrate de apagar el aire acondicionado\n→ Saldos pendientes: recibirás datos de pago por WhatsApp', verbose_name='Check-out Domingo-Jueves')),
                ('checkout_finde', models.TextField(blank=True, default='Viernes y Sábado (desde 10:30 hrs):\n→ Check-out presencial en recepción\n→ Para abrir portón automático, solicitar por WhatsApp', verbose_name='Check-out Viernes-Sábado')),

                # Tips específicos tinas/masajes
                ('recordatorio_toallas', models.TextField(blank=True, default='Recuerde traer toallas. También tenemos toallas para arrendar ($3.000 c/u) o puede usar las de su cabaña si tiene alojamiento.', verbose_name='Recordatorio: Traer Toallas')),
                ('tip_puntualidad', models.TextField(blank=True, default='En Puerto Varas a toda hora hay congestión vehicular. Intente llegar 15 minutos antes de su reserva.', verbose_name='Tip: Puntualidad')),
                ('info_vestidores', models.TextField(blank=True, default='Cada tina tiene su vestidor y también hay vestidores en el spa si gusta utilizar.', verbose_name='Info: Vestidores')),
                ('ropa_masaje', models.TextField(blank=True, default='Para pasajeros que sólo vengan a masaje, traer solamente ropa de interior, no traje de baño.', verbose_name='Info: Ropa para Masaje')),
                ('menores_edad', models.TextField(blank=True, default='Los menores de edad en todo momento deben estar bajo el cuidado de los padres (desde 2 años si utiliza tina de agua caliente o fría, de ser con pañal de agua).', verbose_name='Info: Menores de Edad')),

                # WiFi otras áreas
                ('wifi_tinas', models.CharField(blank=True, default='Red: Tinas / Clave: 82551551', max_length=200, verbose_name='WiFi Sector Tinas')),
                ('wifi_tinajas', models.CharField(blank=True, default='Red: wifi Tinajas / Clave: 12345678', max_length=200, verbose_name='WiFi Tinajas')),
                ('wifi_masajes', models.CharField(blank=True, default='Red: domo / Clave: Tepa2021', max_length=200, verbose_name='WiFi Sala Masajes')),

                # Uso de tinas
                ('uso_tinas_alternancia', models.TextField(blank=True, default='✓ Alterna entre tina caliente y tina fría (Tina Yate - uso libre sin costo)\n✓ Máximo 15 minutos por sesión en agua caliente\n✓ Descansa al borde unos minutos entre sesiones\n✓ Completa hasta 2 horas totales de baño', verbose_name='Uso de Tinas: Alternancia')),
                ('uso_tinas_prohibiciones', models.TextField(blank=True, default='❌ NO usar shampoo, jabones, sales, hierbas ni flores\n❌ NO sumergir la cabeza - el agua está clorada (disposición sanitaria)', verbose_name='Uso de Tinas: Prohibiciones')),
                ('recomendacion_ducha_masaje', models.TextField(blank=True, default='Por recomendación de la masajista, ducharse después del masaje.', verbose_name='Recomendación: Ducha post-masaje')),
                ('prohibicion_vasos', models.TextField(blank=True, default='NO transitar por pasarelas con copas o vasos. Si necesitas, solicita por WhatsApp y te facilitamos vasos para tu hora de tina.', verbose_name='Prohibición: Vasos en Pasarelas')),

                # Seguridad pasarelas
                ('seguridad_pasarelas', models.TextField(blank=True, default='⚠️ SEGURIDAD EN PASARELAS (OBLIGATORIO)\n\nPor tu seguridad al transitar por las pasarelas:\n\n✓ Usar zapatos cómodos y antideslizantes\n✓ Uso de pasamanos OBLIGATORIO\n❌ Prohibido: chalas, zapatos con taco o plataforma\n\nNota: Indicaciones de la autoridad sanitaria', verbose_name='Seguridad en Pasarelas')),

                # Horarios
                ('horario_porton_semana', models.CharField(blank=True, default='Domingo a Jueves: 09:00 - 22:00 hrs', max_length=200, verbose_name='Horario Portón (Dom-Jue)')),
                ('horario_porton_finde', models.CharField(blank=True, default='Viernes y Sábado: 09:00 - 00:00 hrs', max_length=200, verbose_name='Horario Portón (Vie-Sáb)')),
                ('telefono_porton', models.CharField(blank=True, default='+56 9 5336 1647', max_length=50, verbose_name='Teléfono para abrir portón')),
                ('horario_recepcion_semana', models.CharField(blank=True, default='Lunes a Jueves: hasta 20:00 hrs', max_length=200, verbose_name='Horario Recepción (Lun-Jue)')),
                ('horario_recepcion_finde', models.CharField(blank=True, default='Viernes y Sábado: hasta 23:30 hrs', max_length=200, verbose_name='Horario Recepción (Vie-Sáb)')),
                ('horario_recepcion_domingo', models.CharField(blank=True, default='Domingo: hasta 19:30 hrs', max_length=200, verbose_name='Horario Recepción (Dom)')),
                ('horario_cafeteria_semana', models.CharField(blank=True, default='Domingo a Jueves: hasta 20:00 hrs', max_length=200, verbose_name='Horario Cafetería (Dom-Jue)')),
                ('horario_cafeteria_finde', models.CharField(blank=True, default='Viernes y Sábado: hasta 23:00 hrs', max_length=200, verbose_name='Horario Cafetería (Vie-Sáb)')),

                # Cafetería
                ('productos_cafeteria', models.TextField(blank=True, default='Tablas de quesos, jugos naturales, agua con/sin gas, bebidas envasadas', verbose_name='Productos Cafetería')),
                ('menu_cafe', models.TextField(blank=True, default='Café Marley: Capuccino, Mokaccino, Chocolate, Americano, Vainilla, Cortado', verbose_name='Menú de Café')),

                # Ubicación
                ('direccion', models.CharField(blank=True, default='Río Pescado Km 4, Puerto Varas', max_length=200, verbose_name='Dirección')),
                ('como_llegar', models.TextField(blank=True, default='Desde Puerto Varas:\n1. Tomar camino Ensenada hasta km 19 (carretera 255)\n2. Encontrarás retén de Carabineros de Río Pescado (a tu derecha)\n3. Frente al retén, tomar camino de tierra hacia Volcán Calbuco\n   (ANTES del Puente Río Pescado - hay 2 retenes, nosotros estamos en el 1°)\n4. Ingresar 4 km por ese camino\n5. Aremko estará a tu izquierda', verbose_name='Cómo Llegar')),
                ('link_google_maps', models.URLField(blank=True, default='https://maps.google.com/maps?q=-41.2776517%2C-72.7685313&z=17&hl=es', verbose_name='Link Google Maps')),

                # Despedida
                ('despedida', models.TextField(blank=True, default='¡Disfruta tu estadía en Aremko! 🌿✨', verbose_name='Despedida')),
                ('contacto_whatsapp', models.CharField(blank=True, default='+56 9 5336 1647', max_length=50, verbose_name='WhatsApp de Contacto')),
            ],
            options={
                'verbose_name': 'Configuración de Tips Post-Pago',
                'verbose_name_plural': 'Configuración de Tips Post-Pago',
            },
        ),
    ]
