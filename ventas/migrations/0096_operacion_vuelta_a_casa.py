"""
Migración: estructura de Operación Vuelta a Casa (Plan retención WhatsApp).

Esta migración crea:

1. 3 campos nuevos en Cliente:
     - opt_out_whatsapp           (bloqueante permanente)
     - proximo_contacto_no_antes_de (período de gracia)
     - ultimo_contacto_outbound   (regla anti-saturación 30 días)

2. 4 modelos nuevos:
     - ScriptWhatsApp        — catálogo editable de plantillas
     - ContactoWhatsApp      — log de cada intento de contacto sugerido
     - TaxonomiaMovimiento   — bitácora viva de cambios de tramo
     - EventoCelebracion     — hitos para destacar en la bandeja

No requiere data backfill: los nuevos campos en Cliente tienen defaults seguros
(False / NULL) y las tablas nuevas se pueblan vía:
  - generar_bandeja_whatsapp_diaria (cron 06:00)
  - cruzar_reservas_contactos_whatsapp (cron 23:30)
  - recalcular_taxonomia_clientes (cron 05:30, extendido en Etapa 5)

Las 13 plantillas iniciales se cargan vía data migration 0097 (Etapa 2).

Se ejecuta manual en Render con `python manage.py migrate ventas` después de
hacer pull de este commit.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0095_clientetaxonomia'),
    ]

    operations = [
        # ============================================================
        # 1. Campos nuevos en Cliente
        # ============================================================
        migrations.AddField(
            model_name='cliente',
            name='opt_out_whatsapp',
            field=models.BooleanField(
                default=False,
                help_text='Cliente pidió no recibir más WhatsApp. Bloqueante permanente.',
            ),
        ),
        migrations.AddField(
            model_name='cliente',
            name='proximo_contacto_no_antes_de',
            field=models.DateField(
                blank=True, null=True,
                help_text=(
                    "No contactar antes de esta fecha. Usado para 'más adelante' "
                    "y períodos de gracia (90 días tras 'no aplica')."
                ),
            ),
        ),
        migrations.AddField(
            model_name='cliente',
            name='ultimo_contacto_outbound',
            field=models.DateField(
                blank=True, null=True,
                help_text=(
                    'Última vez que enviamos WhatsApp outbound. '
                    'Usado por la regla anti-saturación de 30 días.'
                ),
            ),
        ),

        # ============================================================
        # 2. ScriptWhatsApp — catálogo editable de plantillas
        # ============================================================
        migrations.CreateModel(
            name='ScriptWhatsApp',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('script_id', models.CharField(
                    max_length=10, unique=True, db_index=True,
                    help_text="Convención: 'A.1', 'B.2', etc. Letra=grupo, número=variante.",
                )),
                ('nombre', models.CharField(
                    max_length=120,
                    help_text="Ej: 'En Riesgo · Amante Tinas × Pareja · 1ª salva'",
                )),
                ('estado_valor_target', models.CharField(
                    max_length=40,
                    db_index=True,
                    choices=[
                        ('Campeón', 'Campeón'),
                        ('Leal', 'Leal'),
                        ('Gran Gastador Ocasional', 'Gran Gastador Ocasional'),
                        ('Regular', 'Regular'),
                        ('En Prueba', 'En Prueba'),
                        ('En Riesgo', 'En Riesgo'),
                        ('Dormido', 'Dormido'),
                        ('Pre-sistema', 'Pre-sistema'),
                    ],
                    help_text='Estado de valor del cliente al que va dirigido este script.',
                )),
                ('cohorte_estilo', models.CharField(
                    max_length=40, blank=True,
                    choices=[
                        ('', '— Cualquier estilo —'),
                        ('Devoto del Masaje', 'Devoto del Masaje'),
                        ('Amante de las Tinas', 'Amante de las Tinas'),
                        ('Experiencia Completa', 'Experiencia Completa'),
                        ('Buscador de Alojamiento', 'Buscador de Alojamiento'),
                        ('Probador Esporádico', 'Probador Esporádico'),
                        ('N/A (pre-sistema)', 'N/A (pre-sistema)'),
                    ],
                    help_text='Vacío = aplica a cualquier estilo.',
                )),
                ('cohorte_contexto', models.CharField(
                    max_length=40, blank=True,
                    choices=[
                        ('', '— Cualquier contexto —'),
                        ('Pareja Romántica', 'Pareja Romántica'),
                        ('Auto-cuidado Solo', 'Auto-cuidado Solo'),
                        ('Grupo', 'Grupo'),
                        ('Familiar', 'Familiar'),
                        ('Turista Estacional', 'Turista Estacional'),
                        ('Local Frecuente', 'Local Frecuente'),
                        ('Visitante Solo', 'Visitante Solo'),
                        ('Visitante Pareja', 'Visitante Pareja'),
                        ('Visitante Grupal', 'Visitante Grupal'),
                        ('Sin clasificar', 'Sin clasificar'),
                        ('N/A (pre-sistema)', 'N/A (pre-sistema)'),
                    ],
                    help_text='Vacío = aplica a cualquier contexto.',
                )),
                ('salva', models.PositiveSmallIntegerField(
                    default=1,
                    choices=[(1, '1ª salva'), (2, '2ª salva'), (3, '3ª salva')],
                    help_text='1 = primer contacto, 2 = si no respondió a la 1, 3 = última.',
                )),
                ('plantilla_texto', models.TextField(
                    help_text=(
                        'Texto con placeholders: {nombre}, {ultima_visita_humanizada}, '
                        '{dias_sin_venir}, {ultimo_servicio}, {compania_habitual}, '
                        '{servicio_recomendado}, {sugerencia_dia}, {sugerencia_hora}, '
                        '{cupon_codigo}, {mes_proximo}, {fecha_limite}.'
                    ),
                )),
                ('activo', models.BooleanField(
                    default=True,
                    help_text='Permite desactivar plantilla sin borrarla (A/B testing futuro).',
                )),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('modificado', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Script WhatsApp',
                'verbose_name_plural': 'Scripts WhatsApp',
                'ordering': ['script_id'],
            },
        ),
        migrations.AddIndex(
            model_name='scriptwhatsapp',
            index=models.Index(
                fields=['estado_valor_target', 'cohorte_estilo', 'cohorte_contexto', 'salva'],
                name='idx_script_match',
            ),
        ),
        migrations.AddIndex(
            model_name='scriptwhatsapp',
            index=models.Index(
                fields=['estado_valor_target', 'activo'],
                name='idx_script_estado_activo',
            ),
        ),

        # ============================================================
        # 3. ContactoWhatsApp — log de intentos de contacto
        # ============================================================
        migrations.CreateModel(
            name='ContactoWhatsApp',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),

                # Snapshot del estado del cliente al generar
                ('eje_valor_snapshot', models.CharField(max_length=40)),
                ('eje_estilo_snapshot', models.CharField(max_length=40)),
                ('eje_contexto_snapshot', models.CharField(max_length=40)),
                ('dias_sin_venir_snapshot', models.PositiveIntegerField(
                    blank=True, null=True,
                    help_text='Null si el cliente nunca había venido (edge case Pre-sistema).',
                )),
                ('gasto_historico_snapshot', models.IntegerField(
                    default=0,
                    help_text='CLP, sin decimales (consistente con ClienteTaxonomia.gasto_total).',
                )),

                ('salva', models.PositiveSmallIntegerField(
                    default=1,
                    help_text='1, 2 o 3. Cuál intento es para este cliente.',
                )),
                ('mensaje_renderizado', models.TextField(
                    help_text='Texto YA con variables resueltas, listo para copiar/pegar.',
                )),
                ('prioridad', models.PositiveSmallIntegerField(
                    default=5,
                    help_text='1-6. Define orden de aparición en la bandeja (1 = más urgente).',
                )),
                ('fecha_sugerido', models.DateField(
                    db_index=True,
                    help_text='Día en que el cron lo agregó a la bandeja.',
                )),
                ('estado', models.CharField(
                    max_length=20,
                    default='pendiente',
                    db_index=True,
                    choices=[
                        ('pendiente', 'Pendiente'),
                        ('enviado', 'Enviado'),
                        ('omitido', 'Omitido (sin enviar)'),
                        ('no_aplica', 'No aplica'),
                        ('descartado', 'Descartado por revalidación'),
                    ],
                )),
                ('fecha_envio', models.DateTimeField(blank=True, null=True)),
                ('operador', models.CharField(
                    max_length=100, blank=True,
                    help_text="Usuario que marcó como enviado (ej. 'deborah').",
                )),
                ('mensaje_enviado_editado', models.TextField(
                    blank=True,
                    help_text=(
                        'Si el operador editó el mensaje sugerido antes de enviar, '
                        'guardar el real aquí. Vacío = se envió mensaje_renderizado tal cual.'
                    ),
                )),

                # Tracking de respuesta
                ('respondio', models.BooleanField(default=False)),
                ('fecha_respuesta', models.DateTimeField(blank=True, null=True)),
                ('tipo_respuesta', models.CharField(
                    max_length=30, blank=True,
                    choices=[
                        ('reservo', 'Reservó'),
                        ('interesado', 'Respondió interesada/o'),
                        ('consulto_precio', 'Pidió precio'),
                        ('mas_adelante', 'Más adelante'),
                        ('rechazo', 'Rechazó'),
                        ('opt_out', 'Pidió no escribir más'),
                        ('sin_respuesta', 'Sin respuesta'),
                    ],
                )),
                ('nota_operador', models.TextField(blank=True)),

                # Atribución de conversión
                ('convirtio', models.BooleanField(default=False)),
                ('fecha_atribucion', models.DateTimeField(blank=True, null=True)),

                ('creado', models.DateTimeField(auto_now_add=True)),

                # FKs
                ('cliente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='contactos_whatsapp',
                    to='ventas.cliente',
                )),
                ('script', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='contactos',
                    to='ventas.scriptwhatsapp',
                    help_text='PROTECT: no permitir borrar scripts con histórico de uso.',
                )),
                ('reserva_atribuida', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    blank=True, null=True,
                    related_name='whatsapp_atribuidos',
                    to='ventas.ventareserva',
                    help_text='VentaReserva creada por el cliente dentro de los 30 días posteriores al envío.',
                )),
            ],
            options={
                'verbose_name': 'Contacto WhatsApp',
                'verbose_name_plural': 'Contactos WhatsApp',
            },
        ),
        migrations.AddIndex(
            model_name='contactowhatsapp',
            index=models.Index(fields=['fecha_sugerido', 'estado'], name='idx_cwa_fecha_estado'),
        ),
        migrations.AddIndex(
            model_name='contactowhatsapp',
            index=models.Index(fields=['cliente', 'fecha_envio'], name='idx_cwa_cliente_envio'),
        ),
        migrations.AddIndex(
            model_name='contactowhatsapp',
            index=models.Index(fields=['estado', 'fecha_envio'], name='idx_cwa_estado_envio'),
        ),
        migrations.AddIndex(
            model_name='contactowhatsapp',
            index=models.Index(fields=['convirtio', 'fecha_atribucion'], name='idx_cwa_conv_atrib'),
        ),
        migrations.AddConstraint(
            model_name='contactowhatsapp',
            constraint=models.UniqueConstraint(
                fields=['cliente', 'fecha_sugerido'],
                condition=models.Q(estado='pendiente'),
                name='unique_pendiente_por_cliente_dia',
            ),
        ),

        # ============================================================
        # 4. TaxonomiaMovimiento — bitácora viva de cambios de tramo
        # ============================================================
        migrations.CreateModel(
            name='TaxonomiaMovimiento',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(db_index=True)),

                # Estado anterior
                ('eje_valor_antes', models.CharField(max_length=40)),
                ('eje_estilo_antes', models.CharField(max_length=40)),
                ('eje_contexto_antes', models.CharField(max_length=40)),

                # Estado nuevo
                ('eje_valor_despues', models.CharField(max_length=40)),
                ('eje_estilo_despues', models.CharField(max_length=40)),
                ('eje_contexto_despues', models.CharField(max_length=40)),

                ('evento_origen', models.CharField(
                    max_length=20,
                    choices=[
                        ('reserva', 'Nueva reserva'),
                        ('paso_tiempo', 'Paso del tiempo sin venir'),
                        ('recalculo_features', 'Recálculo features'),
                        ('manual', 'Ajuste manual'),
                    ],
                )),
                ('creado', models.DateTimeField(auto_now_add=True)),

                # FKs
                ('cliente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='movimientos_taxonomia',
                    to='ventas.cliente',
                )),
                ('reserva_relacionada', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    blank=True, null=True,
                    related_name='movimientos_taxonomia',
                    to='ventas.ventareserva',
                    help_text="Reserva que causó el movimiento (si evento_origen='reserva').",
                )),
                ('contacto_whatsapp_atribuido', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    blank=True, null=True,
                    related_name='movimientos_causados',
                    to='ventas.contactowhatsapp',
                    help_text=(
                        'Si hubo WhatsApp en los 30 días previos al movimiento positivo, '
                        'atribuir al contacto más reciente.'
                    ),
                )),
            ],
            options={
                'verbose_name': 'Movimiento de Taxonomía',
                'verbose_name_plural': 'Movimientos de Taxonomía',
            },
        ),
        migrations.AddIndex(
            model_name='taxonomiamovimiento',
            index=models.Index(
                fields=['fecha', 'eje_valor_antes', 'eje_valor_despues'],
                name='idx_tm_fecha_valor',
            ),
        ),
        migrations.AddIndex(
            model_name='taxonomiamovimiento',
            index=models.Index(fields=['cliente', 'fecha'], name='idx_tm_cliente_fecha'),
        ),

        # ============================================================
        # 5. EventoCelebracion — hitos para destacar en la bandeja
        # ============================================================
        migrations.CreateModel(
            name='EventoCelebracion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(
                    max_length=30,
                    choices=[
                        ('recuperado_dormido', 'Recuperado de Dormido'),
                        ('consolidacion_regular', 'En Prueba → Regular'),
                        ('migracion_devoto', 'Probador → Devoto/Amante'),
                        ('trajo_acompanante', 'Solo → Pareja/Grupo'),
                        ('subio_a_leal', 'Subió a Leal'),
                        ('subio_a_campeon', 'Subió a Campeón'),
                    ],
                )),
                ('fecha', models.DateField()),
                ('mensaje_sugerido', models.TextField(
                    blank=True,
                    help_text='Mensaje de agradecimiento sugerido al operador.',
                )),
                ('mostrado_en_bandeja', models.BooleanField(default=False)),
                ('fecha_mostrado', models.DateTimeField(blank=True, null=True)),
                ('creado', models.DateTimeField(auto_now_add=True)),

                # FKs
                ('cliente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='celebraciones',
                    to='ventas.cliente',
                )),
                ('movimiento_relacionado', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='celebraciones',
                    to='ventas.taxonomiamovimiento',
                )),
            ],
            options={
                'verbose_name': 'Evento de Celebración',
                'verbose_name_plural': 'Eventos de Celebración',
            },
        ),
        migrations.AddIndex(
            model_name='eventocelebracion',
            index=models.Index(
                fields=['fecha', 'mostrado_en_bandeja'],
                name='idx_evt_fecha_mostrado',
            ),
        ),
        migrations.AddIndex(
            model_name='eventocelebracion',
            index=models.Index(fields=['cliente', 'fecha'], name='idx_evt_cliente_fecha'),
        ),
    ]
