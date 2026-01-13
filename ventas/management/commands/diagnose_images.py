from django.core.management.base import BaseCommand
from django.conf import settings
from ventas.models import Servicio, Producto
import os


class Command(BaseCommand):
    help = 'Diagnostica problemas con la visualización de imágenes'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS('DIAGNÓSTICO DE IMÁGENES'))
        self.stdout.write(self.style.SUCCESS('='*60))

        # 1. Variables de entorno de Cloudinary
        self.stdout.write('\n1. VARIABLES DE ENTORNO CLOUDINARY:')
        cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
        api_key = os.getenv('CLOUDINARY_API_KEY')
        api_secret = os.getenv('CLOUDINARY_API_SECRET')

        if cloud_name:
            self.stdout.write(f'   ✓ CLOUDINARY_CLOUD_NAME: {cloud_name}')
        else:
            self.stdout.write(self.style.ERROR('   ✗ CLOUDINARY_CLOUD_NAME: NO CONFIGURADO'))

        if api_key:
            self.stdout.write(f'   ✓ CLOUDINARY_API_KEY: {api_key[:10]}...')
        else:
            self.stdout.write(self.style.ERROR('   ✗ CLOUDINARY_API_KEY: NO CONFIGURADO'))

        if api_secret:
            self.stdout.write(f'   ✓ CLOUDINARY_API_SECRET: {api_secret[:10]}...')
        else:
            self.stdout.write(self.style.ERROR('   ✗ CLOUDINARY_API_SECRET: NO CONFIGURADO'))

        # 2. Configuración de Django
        self.stdout.write('\n2. CONFIGURACIÓN DE DJANGO:')
        self.stdout.write(f'   DEFAULT_FILE_STORAGE: {settings.DEFAULT_FILE_STORAGE}')
        self.stdout.write(f'   MEDIA_URL: {getattr(settings, "MEDIA_URL", "NO DEFINIDO")}')

        if hasattr(settings, 'CLOUDINARY_STORAGE'):
            self.stdout.write(f'   CLOUDINARY_STORAGE configurado: SÍ')
        else:
            self.stdout.write(self.style.WARNING('   CLOUDINARY_STORAGE configurado: NO'))

        # 3. Servicios con imágenes
        self.stdout.write('\n3. SERVICIOS CON IMÁGENES:')
        servicios_con_imagen = Servicio.objects.filter(imagen__isnull=False).exclude(imagen='')
        servicios_sin_imagen = Servicio.objects.filter(imagen='') | Servicio.objects.filter(imagen__isnull=True)

        self.stdout.write(f'   Total servicios: {Servicio.objects.count()}')
        self.stdout.write(f'   Servicios con imagen: {servicios_con_imagen.count()}')
        self.stdout.write(f'   Servicios sin imagen: {servicios_sin_imagen.count()}')

        # 4. Ejemplos de URLs de imágenes
        if servicios_con_imagen.exists():
            self.stdout.write('\n4. EJEMPLOS DE URLs GENERADAS:')
            for servicio in servicios_con_imagen[:3]:
                self.stdout.write(f'\n   Servicio: {servicio.nombre}')
                self.stdout.write(f'   Campo imagen: {servicio.imagen}')
                try:
                    url = servicio.imagen.url
                    self.stdout.write(f'   URL generada: {url}')

                    # Verificar si la URL parece correcta
                    if 'cloudinary.com' in url:
                        self.stdout.write(self.style.SUCCESS('   ✓ URL parece ser de Cloudinary'))
                    elif url.startswith('/media/'):
                        self.stdout.write(self.style.WARNING('   ⚠ URL es local (/media/) - NO es Cloudinary'))
                    else:
                        self.stdout.write(self.style.WARNING(f'   ⚠ URL no reconocida'))

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'   ✗ ERROR al generar URL: {e}'))

        # 5. Productos con imágenes
        self.stdout.write('\n5. PRODUCTOS CON IMÁGENES:')
        productos_con_imagen = Producto.objects.filter(imagen__isnull=False).exclude(imagen='')
        productos_sin_imagen = Producto.objects.filter(imagen='') | Producto.objects.filter(imagen__isnull=True)

        self.stdout.write(f'   Total productos: {Producto.objects.count()}')
        self.stdout.write(f'   Productos con imagen: {productos_con_imagen.count()}')
        self.stdout.write(f'   Productos sin imagen: {productos_sin_imagen.count()}')

        # 6. Recomendaciones
        self.stdout.write('\n' + '='*60)
        self.stdout.write('RECOMENDACIONES:')
        self.stdout.write('='*60)

        if not cloud_name or not api_key or not api_secret:
            self.stdout.write(self.style.ERROR('\n⚠️ PROBLEMA CRÍTICO: Variables de Cloudinary no configuradas'))
            self.stdout.write('   Debes configurar en Render:')
            self.stdout.write('   - CLOUDINARY_CLOUD_NAME')
            self.stdout.write('   - CLOUDINARY_API_KEY')
            self.stdout.write('   - CLOUDINARY_API_SECRET')

        if servicios_con_imagen.count() == 0:
            self.stdout.write(self.style.WARNING('\n⚠️ No hay servicios con imágenes subidas'))
            self.stdout.write('   Necesitas subir imágenes desde el admin de Django')

        if hasattr(settings, 'MEDIA_URL') and '/media/' in settings.MEDIA_URL:
            if cloud_name:
                self.stdout.write(self.style.WARNING('\n⚠️ MEDIA_URL está configurado como local pero Cloudinary está disponible'))
                self.stdout.write('   Esto indica que el código no detecta las credenciales correctamente')

        self.stdout.write('\n' + '='*60)
