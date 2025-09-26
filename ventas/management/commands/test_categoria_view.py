# -*- coding: utf-8 -*-
"""
Management command para probar la vista de categoría y diagnosticar el error 500
Uso: python manage.py test_categoria_view --categoria-id 1
"""

from django.core.management.base import BaseCommand, CommandError
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
import traceback

from ventas.models import CategoriaServicio
from ventas.views.public_views import categoria_detail_view

class Command(BaseCommand):
    help = 'Prueba la vista de categoría para diagnosticar errores 500'

    def add_arguments(self, parser):
        parser.add_argument(
            '--categoria-id',
            type=int,
            help='ID de la categoría a probar'
        )
        parser.add_argument(
            '--list-categorias',
            action='store_true',
            help='Listar todas las categorías disponibles'
        )

    def handle(self, *args, **options):
        """
        Prueba la vista de categoría y muestra errores detallados
        """
        if options.get('list_categorias'):
            self.list_categorias()
            return

        categoria_id = options.get('categoria_id')
        if not categoria_id:
            raise CommandError('Debes especificar --categoria-id o --list-categorias')

        self.test_categoria_view(categoria_id)

    def list_categorias(self):
        """Lista todas las categorías disponibles"""
        categorias = CategoriaServicio.objects.all()
        
        self.stdout.write("📋 CATEGORÍAS DISPONIBLES:")
        self.stdout.write("=" * 50)
        
        for categoria in categorias:
            self.stdout.write(f"🔸 ID {categoria.id}: {categoria.nombre}")
        
        if not categorias.exists():
            self.stdout.write("❌ No hay categorías en la base de datos")

    def test_categoria_view(self, categoria_id):
        """Prueba la vista de categoría específica"""
        self.stdout.write(f"🔍 PROBANDO VISTA DE CATEGORÍA ID {categoria_id}")
        self.stdout.write("=" * 60)
        
        try:
            # Verificar que la categoría existe
            categoria = CategoriaServicio.objects.get(id=categoria_id)
            self.stdout.write(f"✅ Categoría encontrada: {categoria.nombre}")
            
            # Crear request simulado
            factory = RequestFactory()
            request = factory.get(f'/categoria/{categoria_id}/')
            request.user = AnonymousUser()
            request.session = {}
            
            # Probar la vista
            self.stdout.write("🧪 Ejecutando vista categoria_detail_view...")
            
            response = categoria_detail_view(request, categoria_id)
            
            self.stdout.write(f"✅ Vista ejecutada exitosamente")
            self.stdout.write(f"📊 Status code: {response.status_code}")
            self.stdout.write(f"📄 Template: category_detail.html")
            
            # Verificar el contenido del contexto
            if hasattr(response, 'context_data'):
                context = response.context_data
                self.stdout.write("📋 Variables de contexto:")
                for key, value in context.items():
                    if hasattr(value, '__len__') and not isinstance(value, str):
                        self.stdout.write(f"   • {key}: {len(value)} elementos")
                    else:
                        self.stdout.write(f"   • {key}: {type(value).__name__}")
            
            self.stdout.write("✅ La vista funciona correctamente en modo local")
            
        except CategoriaServicio.DoesNotExist:
            self.stdout.write(f"❌ Categoría con ID {categoria_id} no encontrada")
            self.list_categorias()
            
        except Exception as e:
            self.stdout.write(f"❌ ERROR EN LA VISTA:")
            self.stdout.write(f"   Tipo: {type(e).__name__}")
            self.stdout.write(f"   Mensaje: {str(e)}")
            self.stdout.write("📋 Traceback completo:")
            self.stdout.write(traceback.format_exc())
            
            # Sugerencias de solución
            self.stdout.write("\n💡 POSIBLES SOLUCIONES:")
            if "DoesNotExist" in str(e):
                self.stdout.write("   • Verificar que el ID de categoría existe")
            elif "template" in str(e).lower():
                self.stdout.write("   • Verificar que el template category_detail.html existe")
            elif "context" in str(e).lower():
                self.stdout.write("   • Verificar las variables del contexto")
            else:
                self.stdout.write("   • Revisar los logs del servidor para más detalles")
                self.stdout.write("   • Verificar la configuración de la base de datos")
                self.stdout.write("   • Verificar que no falten archivos estáticos")