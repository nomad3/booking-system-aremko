"""
Management command para crear el archivo de migración para tramos_validos
Este comando crea el archivo de migración directamente sin usar makemigrations
"""
from django.core.management.base import BaseCommand
import os
from datetime import datetime


class Command(BaseCommand):
    help = 'Crea el archivo de migración para agregar campo tramos_validos'

    def handle(self, *args, **options):
        # Contenido de la migración
        migration_content = '''# Generated manually
from django.db import migrations, models


def migrate_tramo_hito_to_tramos_validos(apps, schema_editor):
    """
    Migra los valores de tramo_hito a tramos_validos
    """
    Premio = apps.get_model('ventas', 'Premio')

    for premio in Premio.objects.all():
        if premio.tramo_hito:
            premio.tramos_validos = [premio.tramo_hito]
            premio.save(update_fields=['tramos_validos'])


def reverse_migration(apps, schema_editor):
    """
    Reversa: toma el primer valor de tramos_validos y lo pone en tramo_hito
    """
    Premio = apps.get_model('ventas', 'Premio')

    for premio in Premio.objects.all():
        if premio.tramos_validos and len(premio.tramos_validos) > 0:
            premio.tramo_hito = premio.tramos_validos[0]
            premio.save(update_fields=['tramo_hito'])


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0058_servicehistory_clientepremio_premio_region_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='premio',
            name='tramos_validos',
            field=models.JSONField(blank=True, default=list, help_text='Lista de tramos donde aplica este premio. Ej: [5,6,7,8] para premio de tramos 5-8'),
        ),
        migrations.AlterField(
            model_name='premio',
            name='tramo_hito',
            field=models.IntegerField(blank=True, help_text='DEPRECATED: Usar tramos_validos. Tramo único antiguo', null=True),
        ),
        migrations.RunPython(migrate_tramo_hito_to_tramos_validos, reverse_migration),
    ]
'''

        # Crear el archivo
        migration_dir = os.path.join('ventas', 'migrations')
        migration_filename = '0059_add_tramos_validos.py'
        migration_path = os.path.join(migration_dir, migration_filename)

        try:
            # Verificar si el directorio existe
            if not os.path.exists(migration_dir):
                os.makedirs(migration_dir)

            # Escribir el archivo
            with open(migration_path, 'w') as f:
                f.write(migration_content)

            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Archivo de migración creado exitosamente: {migration_path}'
                )
            )
            self.stdout.write('\nAhora ejecuta:')
            self.stdout.write('  python manage.py migrate ventas')
            self.stdout.write('  python manage.py configurar_tramos_premios')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'❌ Error creando el archivo de migración: {e}'
                )
            )