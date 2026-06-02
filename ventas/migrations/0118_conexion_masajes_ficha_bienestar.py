import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Conexión-Masajes v1: BienestarMasajeFicha, ParticipanteMasajeReserva,
    SeguimientoBienestarMasaje. Tablas NUEVAS (no alteran existentes) -> seguras
    de desplegar; correr `migrate` MANUAL en Render para crearlas."""

    dependencies = [
        ('ventas', '0117_servicio_video_file'),
    ]

    operations = [
        migrations.CreateModel(
            name='BienestarMasajeFicha',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre_completo', models.CharField(max_length=160)),
                ('telefono', models.CharField(blank=True, max_length=30)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('fecha_nacimiento', models.DateField(blank=True, null=True)),
                ('ciudad', models.CharField(blank=True, max_length=120)),
                ('objetivo_principal', models.CharField(blank=True, max_length=30, choices=[('relajacion', 'Relajación'), ('reducir_estres', 'Reducir estrés'), ('aliviar_tension_muscular', 'Aliviar tensión muscular'), ('descanso', 'Descanso'), ('recuperacion_deportiva', 'Recuperación deportiva'), ('experiencia_pareja', 'Experiencia en pareja'), ('otro', 'Otro')])),
                ('intensidad_preferida', models.CharField(blank=True, max_length=10, choices=[('suave', 'Suave'), ('media', 'Media'), ('firme', 'Firme')])),
                ('zonas_tension', models.CharField(blank=True, max_length=255, verbose_name='Zonas de tensión')),
                ('zonas_evitar', models.CharField(blank=True, max_length=255, verbose_name='Zonas que prefiere evitar')),
                ('observaciones_bienestar', models.TextField(blank=True)),
                ('condiciones_declaradas', models.TextField(blank=True, help_text='Esta información se usa solo para adaptar la experiencia de bienestar. No constituye evaluación médica ni diagnóstico.')),
                ('consentimiento_datos', models.BooleanField(default=False)),
                ('consentimiento_marketing', models.BooleanField(default=False)),
                ('fecha_consentimiento', models.DateTimeField(blank=True, null=True)),
                ('consentimiento_texto', models.TextField(blank=True, help_text='Texto exacto del consentimiento aceptado.')),
                ('origen', models.CharField(default='acompanante', max_length=12, choices=[('comprador', 'Comprador'), ('acompanante', 'Acompañante'), ('recepcion', 'Recepción'), ('admin', 'Admin')])),
                ('estado_ficha', models.CharField(default='pendiente', db_index=True, max_length=12, choices=[('pendiente', 'Pendiente'), ('completada', 'Completada'), ('incompleta', 'Incompleta')])),
                ('obs_terapeuta', models.TextField(blank=True, verbose_name='Observaciones del terapeuta')),
                ('zonas_trabajadas', models.CharField(blank=True, max_length=255)),
                ('intensidad_aplicada', models.CharField(blank=True, max_length=10, choices=[('suave', 'Suave'), ('media', 'Media'), ('firme', 'Firme')])),
                ('sugerencia_frecuencia', models.CharField(blank=True, max_length=15, choices=[('cada_15_dias', 'Cada 15 días'), ('mensual', 'Mensual'), ('cada_2_meses', 'Cada 2 meses'), ('ocasional', 'Ocasional')])),
                ('recomendacion_texto', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cliente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='fichas_bienestar', to='ventas.cliente')),
                ('reserva', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fichas_bienestar', to='ventas.ventareserva')),
                ('servicio_reservado', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='fichas_bienestar', to='ventas.reservaservicio')),
            ],
            options={
                'verbose_name': 'Ficha de bienestar (masaje)',
                'verbose_name_plural': 'Fichas de bienestar (masajes)',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ParticipanteMasajeReserva',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(blank=True, max_length=160)),
                ('telefono', models.CharField(blank=True, max_length=30)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('tipo_participante', models.CharField(max_length=12, choices=[('comprador', 'Comprador'), ('acompanante', 'Acompañante')])),
                ('estado_contacto', models.CharField(default='pendiente', db_index=True, max_length=20, choices=[('pendiente', 'Pendiente'), ('email_enviado', 'Email enviado'), ('formulario_abierto', 'Formulario abierto'), ('ficha_completada', 'Ficha completada'), ('no_responde', 'No responde')])),
                ('token_formulario', models.CharField(blank=True, db_index=True, max_length=64, unique=True)),
                ('fecha_envio', models.DateTimeField(blank=True, null=True)),
                ('fecha_completado_formulario', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reserva', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='participantes_masaje', to='ventas.ventareserva')),
                ('cliente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='participaciones_masaje', to='ventas.cliente')),
                ('ficha_bienestar', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='participante', to='ventas.bienestarmasajeficha')),
            ],
            options={
                'verbose_name': 'Participante de masaje',
                'verbose_name_plural': 'Participantes de masaje',
                'ordering': ['reserva', 'tipo_participante'],
            },
        ),
        migrations.CreateModel(
            name='SeguimientoBienestarMasaje',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo_email', models.CharField(max_length=20, choices=[('gracias_visita', 'Gracias por la visita'), ('encuesta_24h', 'Encuesta 24h'), ('seguimiento_7d', 'Seguimiento 7 días'), ('recomendacion_30d', 'Recomendación 30 días'), ('reactivacion_60d', 'Reactivación 60 días'), ('reactivacion_90d', 'Reactivación 90 días')])),
                ('estado', models.CharField(default='pendiente', db_index=True, max_length=12, choices=[('pendiente', 'Pendiente'), ('enviado', 'Enviado'), ('error', 'Error'), ('cancelado', 'Cancelado')])),
                ('fecha_programada', models.DateTimeField(db_index=True)),
                ('fecha_envio', models.DateTimeField(blank=True, null=True)),
                ('asunto', models.CharField(blank=True, max_length=255)),
                ('cuerpo', models.TextField(blank=True)),
                ('error_log', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('participante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='seguimientos', to='ventas.participantemasajereserva')),
                ('reserva', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='seguimientos_masaje', to='ventas.ventareserva')),
                ('cliente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='seguimientos_masaje', to='ventas.cliente')),
            ],
            options={
                'verbose_name': 'Seguimiento de bienestar (masaje)',
                'verbose_name_plural': 'Seguimientos de bienestar (masajes)',
                'ordering': ['fecha_programada'],
            },
        ),
    ]
