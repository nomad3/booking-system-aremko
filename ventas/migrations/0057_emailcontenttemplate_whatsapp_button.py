# Generated manually on 2025-10-30
from django.db import migrations, models


def update_existing_templates(apps, schema_editor):
    """
    Actualiza templates existentes para usar botón de WhatsApp
    """
    EmailContentTemplate = apps.get_model('ventas', 'EmailContentTemplate')

    # Actualizar todos los templates existentes
    for template in EmailContentTemplate.objects.all():
        template.call_to_action_texto = "📱 Reservar por WhatsApp"
        template.call_to_action_url = "https://wa.me/56957902525?text=Hola%2C%20me%20gustar%C3%ADa%20reservar"
        template.save()

    print(f"✅ Actualizados {EmailContentTemplate.objects.count()} templates con botón WhatsApp")


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0056_cliente_created_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailcontenttemplate',
            name='call_to_action_url',
            field=models.URLField(
                default='https://wa.me/56957902525?text=Hola%2C%20me%20gustar%C3%ADa%20reservar',
                help_text='URL completa del botón. Ej: https://wa.me/56957902525?text=...',
                max_length=500,
                verbose_name='URL del Botón CTA'
            ),
        ),
        migrations.AlterField(
            model_name='emailcontenttemplate',
            name='call_to_action_texto',
            field=models.CharField(
                default='📱 Reservar por WhatsApp',
                max_length=200,
                verbose_name='Texto del Botón CTA'
            ),
        ),
        migrations.RunPython(update_existing_templates, migrations.RunPython.noop),
    ]
