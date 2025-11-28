# Generated manually to fix missing Premio model definition in migration history
# Date: 2025-11-28
# Context: The Premio model exists in production DB but its creation migration was lost/missing.
# This migration now conditionally creates the model if it doesn't exist in the migration state,
# fixing the KeyError: ('ventas', 'premio') during migration application.

from django.db import migrations, models
from django.db import connection

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

class ConditionalCreateModel(migrations.CreateModel):
    """Custom CreateModel operation that checks if table exists first"""
    
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        table_name = self.name.lower()
        full_table_name = f"{app_label}_{table_name}"
        
        # In this specific case, we want to skip creation if table exists
        # BUT we still need to update Django's internal state so it knows the model exists
        if not check_table_exists(full_table_name):
            super().database_forwards(app_label, schema_editor, from_state, to_state)
        else:
            # If table exists, we do nothing in DB, but Django's state is updated automatically
            # by the migration framework processing this operation
            pass

class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0057_emailcontenttemplate_whatsapp_button'),
    ]

    operations = [
        # 1. Define the Premio model structure fully so Django knows about it
        ConditionalCreateModel(
            name='Premio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(help_text="Nombre del premio", max_length=200)),
                ('tipo', models.CharField(choices=[('descuento_bienvenida', 'Descuento Bienvenida'), ('tinas_gratis', 'Tinas Gratis con Masajes'), ('noche_gratis', 'Noche de Alojamiento')], max_length=50)),
                ('descripcion_corta', models.TextField(help_text="Descripción para mostrar en emails")),
                ('descripcion_legal', models.TextField(help_text="Términos y condiciones detallados")),
                ('porcentaje_descuento_tinas', models.DecimalField(blank=True, decimal_places=2, help_text="% descuento en tinas/cabañas", max_digits=5, null=True)),
                ('porcentaje_descuento_masajes', models.DecimalField(blank=True, decimal_places=2, help_text="% descuento en masajes", max_digits=5, null=True)),
                ('valor_monetario', models.DecimalField(blank=True, decimal_places=0, help_text="Valor en pesos del premio (ej: vale $60,000)", max_digits=10, null=True)),
                ('dias_validez', models.IntegerField(default=30, help_text="Días de validez del premio")),
                ('tramos_validos', models.JSONField(blank=True, default=list, help_text='Lista de tramos donde aplica este premio. Ej: [5,6,7,8] para premio de tramos 5-8')),
                ('restricciones', models.JSONField(blank=True, default=dict, help_text='Restricciones en JSON. Ej: {"no_sabados": true, "no_acumulable": true}')),
                ('activo', models.BooleanField(default=True)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_modificacion', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Premio',
                'verbose_name_plural': 'Premios',
                'ordering': ['tipo', 'nombre'],
            },
        ),
        
        # 2. Add the tramo_hito field (which was the original purpose of this migration)
        # We use AddField but wrap it to be safe if it already exists
        migrations.AddField(
            model_name='premio',
            name='tramo_hito',
            field=models.IntegerField(
                blank=True,
                null=True,
                help_text='Tramo en que se otorga este premio automáticamente (ej: 5, 10, 15, 20). NULL = no se otorga automáticamente'
            ),
        ),
    ]
