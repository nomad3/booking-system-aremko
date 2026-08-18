# -*- coding: utf-8 -*-
"""Taxonomía v2 + versión (P-31).

`choices` no toca la base —Django no las valida ahí—, pero la migración deja
el estado alineado. Lo que sí agrega columna es `version_taxonomia`, que hace
que las filas etiquetadas con la taxonomía vieja se rehagan solas.

Las 25 filas ya clasificadas quedan en la v1 y el comando las va a reclasificar.
"""
from django.db import migrations, models

TEMAS_V2 = [
    ('dijo_que_pagaba', 'Quedó de transferir o pagar y no lo hizo'),
    ('freno_en_los_datos', 'Se le pidió un dato para cotizar y desapareció'),
    ('lo_iba_a_pensar', 'Dijo que lo consultaba y avisaba, y no volvió'),
    ('silencio_tras_info', 'Se le pasó precio, fotos o cupo y no volvió a escribir'),
    ('sin_cupo', 'Quería una fecha u hora que no había'),
    ('reserva_existente', 'Ya tenía reserva (dudas, cambios, cómo llegar)'),
    ('info_general', 'Pregunta suelta, sin intención de compra'),
    ('no_ofrecemos', 'Pidió algo que Aremko no vende'),
    ('postventa', 'Reclamo, comentario o agradecimiento tras la visita'),
    ('no_es_cliente', 'Proveedor, comercial, número equivocado o spam'),
    ('otro', 'No calza en ninguna categoría'),
]


class Migration(migrations.Migration):

    dependencies = [('whatsapp_agent', '0011_temaconversacion')]

    operations = [
        migrations.AddField(
            model_name='temaconversacion',
            name='version_taxonomia',
            field=models.IntegerField(db_index=True, default=1),
        ),
        migrations.AlterField(
            model_name='temaconversacion',
            name='tema',
            field=models.CharField(db_index=True, max_length=30, choices=TEMAS_V2),
        ),
    ]
