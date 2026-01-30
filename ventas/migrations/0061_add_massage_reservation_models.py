# Generated manually for massage reservation system
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0060_newslettersubscriber_created_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicio',
            name='permite_reserva_web',
            field=models.BooleanField(
                default=True,
                verbose_name='Permite Reserva Web Directa',
                help_text='Si está marcado, permite reserva directa por web. Si no, requiere contacto por WhatsApp.'
            ),
        ),
        migrations.CreateModel(
            name='SalaServicio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=50, verbose_name='Nombre de la Sala', help_text='Ej: Sala 1, Sala Relax, etc.')),
                ('numero_camillas', models.PositiveIntegerField(default=2, verbose_name='Número de Camillas', help_text='Cantidad de camillas disponibles en esta sala')),
                ('permite_grupos_mixtos', models.BooleanField(default=False, verbose_name='Permite Grupos Mixtos', help_text='Si permite que personas no relacionadas compartan la sala')),
                ('activa', models.BooleanField(default=True, help_text='Si la sala está disponible para uso')),
                ('descripcion', models.TextField(blank=True, help_text='Descripción adicional de la sala')),
            ],
            options={
                'verbose_name': 'Sala de Servicio',
                'verbose_name_plural': 'Salas de Servicio',
                'ordering': ['nombre'],
            },
        ),
        migrations.CreateModel(
            name='MasajistaEspecialidad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nivel_experiencia', models.CharField(
                    max_length=20,
                    choices=[
                        ('basico', 'Básico'),
                        ('intermedio', 'Intermedio'),
                        ('avanzado', 'Avanzado'),
                        ('experto', 'Experto'),
                    ],
                    default='intermedio',
                    help_text='Nivel de experiencia del masajista en este tipo de masaje'
                )),
                ('activo', models.BooleanField(default=True, help_text='Si el masajista está actualmente ofreciendo este servicio')),
                ('masajista', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    limit_choices_to={'es_masajista': True},
                    related_name='especialidades',
                    to='ventas.proveedor',
                    verbose_name='Masajista'
                )),
                ('servicio', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    limit_choices_to={'tipo_servicio': 'masaje'},
                    related_name='especialistas',
                    to='ventas.servicio',
                    verbose_name='Tipo de Masaje'
                )),
            ],
            options={
                'verbose_name': 'Especialidad de Masajista',
                'verbose_name_plural': 'Especialidades de Masajistas',
                'ordering': ['masajista__nombre', 'servicio__nombre'],
                'unique_together': {('masajista', 'servicio')},
            },
        ),
        migrations.CreateModel(
            name='HorarioMasajista',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dia_semana', models.IntegerField(
                    choices=[
                        (0, 'Lunes'),
                        (1, 'Martes'),
                        (2, 'Miércoles'),
                        (3, 'Jueves'),
                        (4, 'Viernes'),
                        (5, 'Sábado'),
                        (6, 'Domingo'),
                    ],
                    verbose_name='Día de la Semana'
                )),
                ('hora_inicio', models.TimeField(verbose_name='Hora de Inicio', help_text='Hora de inicio del turno')),
                ('hora_fin', models.TimeField(verbose_name='Hora de Fin', help_text='Hora de fin del turno')),
                ('disponible', models.BooleanField(default=True, help_text='Si el masajista está disponible este día')),
                ('masajista', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    limit_choices_to={'es_masajista': True},
                    related_name='horarios',
                    to='ventas.proveedor',
                    verbose_name='Masajista'
                )),
            ],
            options={
                'verbose_name': 'Horario de Masajista',
                'verbose_name_plural': 'Horarios de Masajistas',
                'ordering': ['masajista__nombre', 'dia_semana'],
                'unique_together': {('masajista', 'dia_semana')},
            },
        ),
    ]