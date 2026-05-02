"""Migración: agregar tabla EncuestaSatisfaccion (Tarea 1.4 plan maestro).

Sistema de Voice of Customer integrado: reemplaza Google Form externo con
captura nativa a BD para análisis IA semanal.

⚠️ EJECUCIÓN MANUAL — esta migración NO corre automáticamente en deploy.
Debe ejecutarse desde shell de Render con:
    python manage.py migrate ventas 0084_encuestasatisfaccion
"""
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0083_servicio_producto_imagenes_extra'),
    ]

    operations = [
        migrations.CreateModel(
            name='EncuestaSatisfaccion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_respuesta', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('fecha_visita', models.DateField(blank=True, help_text='Fecha de la visita evaluada', null=True)),
                ('origen', models.CharField(
                    choices=[
                        ('formulario_web', 'Formulario web Aremko'),
                        ('legacy_google_form', 'Google Form (legacy)'),
                        ('manual', 'Ingreso manual'),
                    ],
                    default='formulario_web', max_length=30
                )),
                ('contacto_nombre', models.CharField(blank=True, max_length=200)),
                ('contacto_email', models.EmailField(blank=True, max_length=254)),
                ('servicios_contratados', models.JSONField(
                    blank=True, default=list,
                    help_text='Lista: tina_hidromasaje, tina_sin_hidromasaje, masaje, alojamiento'
                )),
                ('cal_temperatura_tina', models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)]
                )),
                ('cal_transparencia_agua', models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)]
                )),
                ('cal_limpieza_tinas', models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)]
                )),
                ('cal_limpieza_cabana', models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)]
                )),
                ('cal_temperatura_cabana', models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)]
                )),
                ('cal_limpieza_sala_masajes', models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)]
                )),
                ('cal_servicio_masajes', models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)]
                )),
                ('cal_calidad_precio', models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)]
                )),
                ('cal_atencion_ventas', models.PositiveSmallIntegerField(
                    blank=True, help_text='Atención por WhatsApp/Instagram/Facebook', null=True,
                    validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)]
                )),
                ('cal_compra_web', models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)]
                )),
                ('cal_atencion_visita', models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)]
                )),
                ('cal_experiencia_general', models.PositiveSmallIntegerField(
                    blank=True, help_text='Calificación global de la experiencia', null=True,
                    validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)]
                )),
                ('nps_score', models.PositiveSmallIntegerField(
                    blank=True, help_text='0-10. Promotores: 9-10. Pasivos: 7-8. Detractores: 0-6', null=True,
                    validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(10)]
                )),
                ('lo_que_mas_gusto', models.TextField(blank=True)),
                ('sugerencias', models.TextField(blank=True)),
                ('decepcion', models.TextField(blank=True, help_text='¿Hubo algo que te decepcionó?')),
                ('como_se_entero', models.CharField(
                    blank=True, max_length=30,
                    choices=[
                        ('soy_cliente', 'Soy cliente recurrente'),
                        ('recomendacion', 'Recomendación de conocido'),
                        ('instagram', 'Instagram'),
                        ('facebook', 'Facebook'),
                        ('google', 'Google / búsqueda'),
                        ('blog', 'Blog Aremko'),
                        ('publicidad', 'Publicidad'),
                        ('otro', 'Otro'),
                    ]
                )),
                ('como_se_entero_otro', models.CharField(blank=True, max_length=200)),
                ('ocasion_visita', models.CharField(
                    blank=True, max_length=30,
                    choices=[
                        ('pareja', 'Escapada en pareja'),
                        ('cumpleanos', 'Cumpleaños'),
                        ('aniversario', 'Aniversario'),
                        ('amigos', 'Amigos'),
                        ('familia', 'Familia'),
                        ('trabajo', 'Trabajo / empresa'),
                        ('solo', 'Solo / sola'),
                        ('otro', 'Otro'),
                    ]
                )),
                ('intencion_volver', models.CharField(
                    blank=True, max_length=30,
                    choices=[
                        ('si_6m', 'Sí, en menos de 6 meses'),
                        ('si_12m', 'Sí, en 6-12 meses'),
                        ('si_mas_1a', 'Sí, en más de 1 año'),
                        ('no_seguro', 'No estoy seguro/a'),
                        ('probablemente_no', 'Probablemente no'),
                    ]
                )),
                ('permite_uso_comentarios_redes', models.BooleanField(
                    blank=True, null=True,
                    help_text='¿Podemos usar tus comentarios anónimos en redes sociales?'
                )),
                ('quiere_newsletter', models.BooleanField(blank=True, null=True)),
                ('permite_seguimiento', models.BooleanField(
                    blank=True, null=True,
                    help_text='¿Podemos contactarte si necesitamos más información?'
                )),
                ('analisis_ia', models.JSONField(
                    blank=True, null=True,
                    help_text='Análisis automático: sentiment, temas, urgencia detectados'
                )),
                ('requiere_followup', models.BooleanField(
                    default=False,
                    help_text='Marcado cuando NPS<=5 o califica 1-2 en alguna dimensión crítica'
                )),
                ('followup_completado', models.BooleanField(default=False)),
                ('followup_notas', models.TextField(blank=True)),
                ('cliente', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='encuestas_satisfaccion', to='ventas.cliente'
                )),
                ('venta_reserva', models.ForeignKey(
                    blank=True, help_text='Reserva específica que motivó esta encuesta', null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='encuestas_satisfaccion', to='ventas.ventareserva'
                )),
            ],
            options={
                'verbose_name': 'Encuesta de satisfacción',
                'verbose_name_plural': 'Encuestas de satisfacción',
                'ordering': ['-fecha_respuesta'],
            },
        ),
        migrations.AddIndex(
            model_name='encuestasatisfaccion',
            index=models.Index(fields=['-fecha_respuesta'], name='ventas_encu_fecha_r_desc_idx'),
        ),
        migrations.AddIndex(
            model_name='encuestasatisfaccion',
            index=models.Index(fields=['cliente'], name='ventas_encu_cliente_idx'),
        ),
        migrations.AddIndex(
            model_name='encuestasatisfaccion',
            index=models.Index(fields=['nps_score'], name='ventas_encu_nps_idx'),
        ),
        migrations.AddIndex(
            model_name='encuestasatisfaccion',
            index=models.Index(fields=['requiere_followup', 'followup_completado'], name='ventas_encu_followup_idx'),
        ),
        migrations.AddIndex(
            model_name='encuestasatisfaccion',
            index=models.Index(fields=['origen'], name='ventas_encu_origen_idx'),
        ),
    ]
