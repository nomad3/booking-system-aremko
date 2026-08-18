# -*- coding: utf-8 -*-
"""Tabla nueva y aislada (P-31): no toca ninguna existente.

Escrita a mano —como todas en este repo— porque `makemigrations` arrastra el
drift de AR-033/034 y pide input interactivo por cambios preexistentes.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_agent', '0010_propuestareserva_reserva_existente_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='TemaConversacion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('telefono', models.CharField(db_index=True, max_length=20, unique=True)),
                ('tema', models.CharField(db_index=True, max_length=30, choices=[
                    ('precio_disponibilidad', 'Preguntó precio o cupo y no siguió'),
                    ('sin_cupo', 'Quería una fecha u hora que no había'),
                    ('reserva_existente', 'Ya tenía reserva (dudas, cambios, cómo llegar)'),
                    ('info_general', 'Información general, sin intención de compra clara'),
                    ('no_ofrecemos', 'Pidió algo que Aremko no vende'),
                    ('postventa', 'Reclamo, comentario o agradecimiento tras la visita'),
                    ('no_es_cliente', 'Proveedor, comercial, número equivocado o spam'),
                    ('quedo_en_pensarlo', 'Interés real: dijo que confirmaba y no volvió'),
                    ('otro', 'No calza en ninguna categoría'),
                ])),
                ('motivo', models.CharField(blank=True, max_length=200)),
                ('confianza', models.CharField(db_index=True, default='media', max_length=6,
                                               choices=[('alta', 'Alta'), ('media', 'Media'),
                                                        ('baja', 'Baja')])),
                ('mensajes_vistos', models.IntegerField(default=0)),
                ('ultimo_mensaje_visto', models.DateTimeField(
                    blank=True, null=True,
                    help_text='Hasta qué mensaje se leyó. Si llegan más nuevos, se reclasifica.')),
                ('modelo', models.CharField(blank=True, max_length=80)),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('actualizado', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Tema de conversación',
                'verbose_name_plural': 'Temas de conversaciones',
                'ordering': ['-actualizado'],
            },
        ),
        migrations.AddIndex(
            model_name='temaconversacion',
            index=models.Index(fields=['tema', 'confianza'],
                               name='idx_tema_conf'),
        ),
    ]
