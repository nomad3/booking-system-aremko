# -*- coding: utf-8 -*-
"""
Comando para actualizar permisos del modelo ServicioBloqueo
Necesario porque la tabla se creó con SQL manual
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.management import create_permissions
from django.apps import apps


class Command(BaseCommand):
    help = 'Actualiza permisos para el modelo ServicioBloqueo'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n🔐 Actualizando permisos de ServicioBloqueo...\n'))

        try:
            # Obtener la app 'ventas'
            app_config = apps.get_app_config('ventas')

            # Crear permisos para todos los modelos de la app
            create_permissions(app_config, verbosity=0)

            self.stdout.write(self.style.SUCCESS('✅ Permisos creados exitosamente!\n'))

            # Verificar que los permisos existen
            from django.contrib.auth.models import Permission
            from django.contrib.contenttypes.models import ContentType
            from ventas.models import ServicioBloqueo

            content_type = ContentType.objects.get_for_model(ServicioBloqueo)
            permisos = Permission.objects.filter(content_type=content_type)

            self.stdout.write(self.style.SUCCESS(f'📋 Permisos encontrados para ServicioBloqueo: {permisos.count()}\n'))

            for permiso in permisos:
                self.stdout.write(f'   ✓ {permiso.codename}: {permiso.name}')

            self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
            self.stdout.write(self.style.SUCCESS('PERMISOS ACTUALIZADOS'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(self.style.SUCCESS('\n💡 Ahora el modelo debería aparecer en el menú del admin'))
            self.stdout.write(self.style.SUCCESS('   Refresca la página del admin (Ctrl+F5 o Cmd+Shift+R)\n'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error actualizando permisos:'))
            self.stdout.write(self.style.ERROR(f'   {str(e)}\n'))
            raise
