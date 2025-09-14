# Generated manually for advanced email campaign system
# Date: 2025-09-14

from django.conf import settings
from django.db import migrations, models, connection
import django.db.models.deletion
import django.utils.timezone


def check_table_exists(table_name):
    """Check if a table exists in the database"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            );
        """, [table_name])
        return cursor.fetchone()[0]


def check_constraint_exists(constraint_name):
    """Check if a constraint exists in the database"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.table_constraints 
                WHERE constraint_schema = 'public' 
                AND constraint_name = %s
            );
        """, [constraint_name])
        return cursor.fetchone()[0]


def check_index_exists(index_name):
    """Check if an index exists in the database"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM pg_indexes 
                WHERE schemaname = 'public' 
                AND indexname = %s
            );
        """, [index_name])
        return cursor.fetchone()[0]


class ConditionalCreateModel(migrations.CreateModel):
    """Custom CreateModel operation that checks if table exists first"""
    
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        table_name = self.name.lower()
        full_table_name = f"{app_label}_{table_name}"
        
        if not check_table_exists(full_table_name):
            # Table doesn't exist, create it normally
            super().database_forwards(app_label, schema_editor, from_state, to_state)
        else:
            # Table exists, just add to Django's migration history
            pass


class ConditionalAlterUniqueTogether(migrations.AlterUniqueTogether):
    """Custom AlterUniqueTogether that checks if constraint exists first"""
    
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        # Generate the constraint name that Django would use
        model = to_state.apps.get_model(app_label, self.name)
        table_name = model._meta.db_table
        
        if self.unique_together:
            for fields in self.unique_together:
                # Django generates constraint names like "appname_modelname_field1_field2_hash_uniq"
                field_names = "_".join(fields)
                # Django uses a hash for the constraint name - we'll check if any constraint exists on these fields
                
                # Check if table has constraints on these fields already
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT tc.constraint_name FROM information_schema.table_constraints tc
                        JOIN information_schema.constraint_column_usage ccu 
                        ON tc.constraint_name = ccu.constraint_name
                        WHERE tc.table_name = %s 
                        AND tc.constraint_type = 'UNIQUE'
                        AND tc.constraint_schema = 'public'
                    """, [table_name])
                    
                    existing_constraints = [row[0] for row in cursor.fetchall()]
                    
                    # If there are any unique constraints, skip creating new ones
                    if any(field_names.replace('_', '') in constraint.replace('_', '') 
                           for constraint in existing_constraints):
                        return
        
        # If no existing constraints found, proceed normally
        super().database_forwards(app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ventas', '0050_homepagesettings'),
    ]

    operations = [
        # Communication Limits
        ConditionalCreateModel(
            name='CommunicationLimit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sms_count_daily', models.IntegerField(default=0, verbose_name='SMS enviados hoy')),
                ('sms_count_monthly', models.IntegerField(default=0, verbose_name='SMS enviados este mes')),
                ('last_sms_date', models.DateField(blank=True, null=True, verbose_name='Fecha último SMS')),
                ('last_sms_reset_daily', models.DateField(auto_now_add=True, verbose_name='Última reset daily')),
                ('last_sms_reset_monthly', models.DateField(auto_now_add=True, verbose_name='Última reset monthly')),
                ('email_count_weekly', models.IntegerField(default=0, verbose_name='Emails enviados esta semana')),
                ('email_count_monthly', models.IntegerField(default=0, verbose_name='Emails enviados este mes')),
                ('last_email_date', models.DateTimeField(blank=True, null=True, verbose_name='Fecha último email')),
                ('last_email_reset_weekly', models.DateField(auto_now_add=True, verbose_name='Última reset weekly')),
                ('last_email_reset_monthly', models.DateField(auto_now_add=True, verbose_name='Última reset monthly')),
                ('birthday_sms_sent_this_year', models.BooleanField(default=False, verbose_name='SMS cumpleaños enviado este año')),
                ('last_birthday_sms_year', models.IntegerField(blank=True, null=True, verbose_name='Año último SMS cumpleaños')),
                ('reactivation_emails_this_quarter', models.IntegerField(default=0, verbose_name='Emails reactivación este trimestre')),
                ('last_reactivation_quarter', models.CharField(blank=True, max_length=7, verbose_name='Último trimestre reactivación (YYYY-Q)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cliente', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='communication_limit', to='ventas.cliente')),
            ],
            options={
                'verbose_name': 'Límite de Comunicación',
                'verbose_name_plural': 'Límites de Comunicación',
            },
        ),
        
        # Client Preferences
        ConditionalCreateModel(
            name='ClientPreferences',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accepts_sms', models.BooleanField(default=True, verbose_name='Acepta SMS')),
                ('accepts_email', models.BooleanField(default=True, verbose_name='Acepta Email')),
                ('accepts_whatsapp', models.BooleanField(default=True, verbose_name='Acepta WhatsApp')),
                ('accepts_booking_confirmations', models.BooleanField(default=True, verbose_name='Acepta confirmaciones de reserva')),
                ('accepts_booking_reminders', models.BooleanField(default=True, verbose_name='Acepta recordatorios de cita')),
                ('accepts_birthday_messages', models.BooleanField(default=True, verbose_name='Acepta mensajes de cumpleaños')),
                ('accepts_promotional', models.BooleanField(default=True, verbose_name='Acepta mensajes promocionales')),
                ('accepts_newsletters', models.BooleanField(default=True, verbose_name='Acepta newsletters')),
                ('accepts_reactivation', models.BooleanField(default=True, verbose_name='Acepta mensajes de reactivación')),
                ('preferred_contact_hour_start', models.TimeField(default=django.utils.timezone.datetime.strptime('09:00', '%H:%M').time(), verbose_name='Hora inicio contacto')),
                ('preferred_contact_hour_end', models.TimeField(default=django.utils.timezone.datetime.strptime('20:00', '%H:%M').time(), verbose_name='Hora fin contacto')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('opt_out_date', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de opt-out general')),
                ('cliente', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='preferences', to='ventas.cliente')),
            ],
            options={
                'verbose_name': 'Preferencia del Cliente',
                'verbose_name_plural': 'Preferencias de los Clientes',
            },
        ),
        
        # Communication Log
        ConditionalCreateModel(
            name='CommunicationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('communication_type', models.CharField(choices=[('SMS', 'SMS'), ('EMAIL', 'Email'), ('WHATSAPP', 'WhatsApp'), ('CALL', 'Llamada')], max_length=20, verbose_name='Tipo comunicación')),
                ('message_type', models.CharField(choices=[('BOOKING_CONFIRMATION', 'Confirmación de reserva'), ('BOOKING_REMINDER', 'Recordatorio de cita'), ('BIRTHDAY', 'Felicitación cumpleaños'), ('PROMOTIONAL', 'Promocional'), ('NEWSLETTER', 'Newsletter'), ('REACTIVATION', 'Reactivación'), ('FOLLOW_UP', 'Seguimiento'), ('SATISFACTION_SURVEY', 'Encuesta satisfacción'), ('OTHER', 'Otro')], max_length=30, verbose_name='Tipo mensaje')),
                ('subject', models.CharField(blank=True, max_length=255, verbose_name='Asunto')),
                ('content', models.TextField(verbose_name='Contenido')),
                ('destination', models.CharField(max_length=100, verbose_name='Destino (teléfono/email)')),
                ('status', models.CharField(choices=[('PENDING', 'Pendiente'), ('SENT', 'Enviado'), ('DELIVERED', 'Entregado'), ('READ', 'Leído'), ('REPLIED', 'Respondido'), ('FAILED', 'Falló'), ('BLOCKED', 'Bloqueado por límites')], default='PENDING', max_length=20, verbose_name='Estado')),
                ('external_id', models.CharField(blank=True, max_length=100, verbose_name='ID externo (batch_id, etc.)')),
                ('sent_at', models.DateTimeField(blank=True, null=True, verbose_name='Enviado en')),
                ('delivered_at', models.DateTimeField(blank=True, null=True, verbose_name='Entregado en')),
                ('read_at', models.DateTimeField(blank=True, null=True, verbose_name='Leído en')),
                ('replied_at', models.DateTimeField(blank=True, null=True, verbose_name='Respondido en')),
                ('cost', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name='Costo')),
                ('booking_id', models.IntegerField(blank=True, null=True, verbose_name='ID Reserva relacionada')),
                ('triggered_by', models.CharField(blank=True, max_length=100, verbose_name='Disparado por')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('campaign', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='communication_logs', to='ventas.campaign')),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='communication_logs', to='ventas.cliente')),
            ],
            options={
                'verbose_name': 'Log de Comunicación',
                'verbose_name_plural': 'Logs de Comunicación',
                'ordering': ['-created_at'],
            },
        ),
        
        # Mail Para Enviar
        ConditionalCreateModel(
            name='MailParaEnviar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=255, verbose_name='Nombre/Empresa')),
                ('email', models.EmailField(max_length=254, verbose_name='Email')),
                ('ciudad', models.CharField(blank=True, max_length=100, verbose_name='Ciudad')),
                ('rubro', models.CharField(blank=True, max_length=100, verbose_name='Rubro')),
                ('asunto', models.CharField(max_length=255, verbose_name='Asunto')),
                ('contenido_html', models.TextField(verbose_name='Contenido HTML')),
                ('estado', models.CharField(choices=[('PENDIENTE', 'Pendiente'), ('ENVIADO', 'Enviado'), ('FALLIDO', 'Fallido'), ('PAUSADO', 'Pausado')], default='PENDIENTE', max_length=20, verbose_name='Estado')),
                ('prioridad', models.IntegerField(default=1, verbose_name='Prioridad (1=alta, 5=baja)')),
                ('creado_en', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('enviado_en', models.DateTimeField(blank=True, null=True, verbose_name='Enviado en')),
                ('campana', models.CharField(blank=True, max_length=100, verbose_name='Campaña')),
                ('notas', models.TextField(blank=True, verbose_name='Notas')),
            ],
            options={
                'verbose_name': 'Mail para Enviar',
                'verbose_name_plural': 'Mails para Enviar',
                'ordering': ['prioridad', 'creado_en'],
            },
        ),
        
        # SMS Template
        ConditionalCreateModel(
            name='SMSTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Nombre plantilla')),
                ('message_type', models.CharField(choices=[('BOOKING_CONFIRMATION', 'Confirmación de reserva'), ('BOOKING_REMINDER', 'Recordatorio de cita'), ('BIRTHDAY', 'Felicitación cumpleaños'), ('REACTIVATION', 'Reactivación'), ('SATISFACTION_SURVEY', 'Encuesta satisfacción'), ('PROMOTIONAL', 'Promocional')], max_length=30, verbose_name='Tipo mensaje')),
                ('content', models.TextField(help_text='Usar {nombre}, {apellido}, {servicio}, {fecha}, {hora} como variables', verbose_name='Contenido')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activa')),
                ('requires_approval', models.BooleanField(default=False, verbose_name='Requiere aprobación')),
                ('max_uses_per_client_per_day', models.IntegerField(default=1, verbose_name='Máximo usos por cliente por día')),
                ('max_uses_per_client_per_month', models.IntegerField(default=4, verbose_name='Máximo usos por cliente por mes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
            ],
            options={
                'verbose_name': 'Plantilla SMS',
                'verbose_name_plural': 'Plantillas SMS',
            },
        ),
        
        # Email Template
        ConditionalCreateModel(
            name='EmailTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Nombre del Template')),
                ('subject', models.CharField(max_length=500, verbose_name='Asunto')),
                ('body_html', models.TextField(verbose_name='Cuerpo HTML')),
                ('campaign_type', models.CharField(choices=[('giftcard', 'Campaña Giftcard'), ('promocional', 'Promocional'), ('recordatorio', 'Recordatorio')], default='giftcard', max_length=50)),
                ('year', models.IntegerField(default=2025, verbose_name='Año')),
                ('month', models.IntegerField(default=1, verbose_name='Mes')),
                ('giftcard_amount', models.IntegerField(default=15000, verbose_name='Monto Giftcard')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Template de Email',
                'verbose_name_plural': 'Templates de Email',
                'ordering': ['-created_at'],
            },
        ),
        
        # Email Campaign (Main model)
        ConditionalCreateModel(
            name='EmailCampaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Nombre de la campaña')),
                ('description', models.TextField(blank=True, verbose_name='Descripción')),
                ('status', models.CharField(choices=[('draft', 'Borrador'), ('ready', 'Lista para envío'), ('sending', 'Enviando'), ('paused', 'Pausada'), ('completed', 'Completada'), ('cancelled', 'Cancelada')], default='draft', max_length=20, verbose_name='Estado')),
                ('criteria', models.JSONField(default=dict, verbose_name='Criterios de selección')),
                ('schedule_config', models.JSONField(default=dict, verbose_name='Configuración de horarios')),
                ('email_subject_template', models.CharField(max_length=500, verbose_name='Template de asunto')),
                ('email_body_template', models.TextField(verbose_name='Template de cuerpo')),
                ('ai_variation_enabled', models.BooleanField(default=True, verbose_name='Usar IA para variar contenido')),
                ('anti_spam_enabled', models.BooleanField(default=True, verbose_name='Medidas anti-spam activas')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('total_recipients', models.IntegerField(default=0, verbose_name='Total de destinatarios')),
                ('emails_sent', models.IntegerField(default=0, verbose_name='Emails enviados')),
                ('emails_delivered', models.IntegerField(default=0, verbose_name='Emails entregados')),
                ('emails_opened', models.IntegerField(default=0, verbose_name='Emails abiertos')),
                ('emails_clicked', models.IntegerField(default=0, verbose_name='Clicks en emails')),
                ('emails_bounced', models.IntegerField(default=0, verbose_name='Emails rebotados')),
                ('spam_complaints', models.IntegerField(default=0, verbose_name='Quejas de spam')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
            ],
            options={
                'verbose_name': 'Campaña de Email',
                'verbose_name_plural': 'Campañas de Email',
                'ordering': ['-created_at'],
            },
        ),
        
        # Email Recipient
        ConditionalCreateModel(
            name='EmailRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254, verbose_name='Email')),
                ('name', models.CharField(max_length=200, verbose_name='Nombre')),
                ('personalized_subject', models.CharField(max_length=500, verbose_name='Asunto personalizado')),
                ('personalized_body', models.TextField(verbose_name='Cuerpo personalizado')),
                ('send_enabled', models.BooleanField(default=True, verbose_name='Habilitado para envío')),
                ('priority', models.IntegerField(default=1, verbose_name='Prioridad')),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('sending', 'Enviando'), ('sent', 'Enviado'), ('delivered', 'Entregado'), ('opened', 'Abierto'), ('clicked', 'Click realizado'), ('bounced', 'Rebotado'), ('failed', 'Fallido'), ('spam_complaint', 'Queja de spam'), ('unsubscribed', 'Desuscrito'), ('excluded', 'Excluido')], default='pending', max_length=20, verbose_name='Estado')),
                ('scheduled_at', models.DateTimeField(blank=True, null=True, verbose_name='Programado para')),
                ('sent_at', models.DateTimeField(blank=True, null=True, verbose_name='Enviado en')),
                ('delivered_at', models.DateTimeField(blank=True, null=True, verbose_name='Entregado en')),
                ('opened_at', models.DateTimeField(blank=True, null=True, verbose_name='Abierto en')),
                ('clicked_at', models.DateTimeField(blank=True, null=True, verbose_name='Click en')),
                ('error_message', models.TextField(blank=True, verbose_name='Mensaje de error')),
                ('bounce_reason', models.CharField(blank=True, max_length=200, verbose_name='Razón del rebote')),
                ('user_agent', models.CharField(blank=True, max_length=500, verbose_name='User Agent')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP Address')),
                ('client_total_spend', models.DecimalField(decimal_places=0, default=0, max_digits=12, verbose_name='Gasto total del cliente')),
                ('client_visit_count', models.IntegerField(default=0, verbose_name='Número de visitas')),
                ('client_last_visit', models.DateField(blank=True, null=True, verbose_name='Última visita')),
                ('client_city', models.CharField(blank=True, max_length=100, verbose_name='Ciudad del cliente')),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recipients', to='ventas.emailcampaign')),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ventas.cliente', verbose_name='Cliente')),
            ],
            options={
                'verbose_name': 'Destinatario de Email',
                'verbose_name_plural': 'Destinatarios de Email',
                'ordering': ['priority', 'scheduled_at', 'id'],
            },
        ),
        
        # Email Delivery Log
        ConditionalCreateModel(
            name='EmailDeliveryLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('log_type', models.CharField(choices=[('send_attempt', 'Intento de envío'), ('delivery_success', 'Entrega exitosa'), ('delivery_failure', 'Falla en entrega'), ('bounce_hard', 'Rebote duro'), ('bounce_soft', 'Rebote suave'), ('spam_complaint', 'Queja de spam'), ('unsubscribe', 'Desuscripción'), ('open_tracking', 'Seguimiento de apertura'), ('click_tracking', 'Seguimiento de clicks')], max_length=20, verbose_name='Tipo de log')),
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='Timestamp')),
                ('smtp_response', models.TextField(blank=True, verbose_name='Respuesta SMTP')),
                ('error_code', models.CharField(blank=True, max_length=10, verbose_name='Código de error')),
                ('error_message', models.TextField(blank=True, verbose_name='Mensaje de error')),
                ('user_agent', models.CharField(blank=True, max_length=500, verbose_name='User Agent')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP Address')),
                ('country_code', models.CharField(blank=True, max_length=2, verbose_name='Código de país')),
                ('server_response_time', models.FloatField(blank=True, null=True, verbose_name='Tiempo de respuesta (ms)')),
                ('retry_count', models.IntegerField(default=0, verbose_name='Número de reintentos')),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='delivery_logs', to='ventas.emailcampaign')),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='delivery_logs', to='ventas.emailrecipient')),
            ],
            options={
                'verbose_name': 'Log de Entrega de Email',
                'verbose_name_plural': 'Logs de Entrega de Email',
                'ordering': ['-timestamp'],
            },
        ),
        
        # Email Blacklist
        ConditionalCreateModel(
            name='EmailBlacklist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='Email')),
                ('reason', models.CharField(choices=[('hard_bounce', 'Rebote duro'), ('spam_complaint', 'Queja de spam'), ('unsubscribe', 'Desuscripción'), ('invalid_email', 'Email inválido'), ('domain_blocked', 'Dominio bloqueado'), ('manual_block', 'Bloqueo manual'), ('suspicious_activity', 'Actividad sospechosa')], max_length=20, verbose_name='Razón del bloqueo')),
                ('added_at', models.DateTimeField(auto_now_add=True, verbose_name='Agregado en')),
                ('notes', models.TextField(blank=True, verbose_name='Notas')),
                ('domain', models.CharField(max_length=100, verbose_name='Dominio')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
                ('expires_at', models.DateTimeField(blank=True, null=True, verbose_name='Expira en')),
                ('added_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Agregado por')),
            ],
            options={
                'verbose_name': 'Email en Lista Negra',
                'verbose_name_plural': 'Emails en Lista Negra',
                'ordering': ['-added_at'],
            },
        ),
        
        # Add constraints and indexes
        ConditionalAlterUniqueTogether(
            name='emailrecipient',
            unique_together={('campaign', 'email')},
        ),
        ConditionalAlterUniqueTogether(
            name='smstemplate',
            unique_together={('name', 'message_type')},
        ),
    ]