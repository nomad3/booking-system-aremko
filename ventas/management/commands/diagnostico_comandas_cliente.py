"""
Comando de diagnóstico para sistema de comandas de clientes vía WhatsApp
Uso: python manage.py diagnostico_comandas_cliente [token]
"""
from django.core.management.base import BaseCommand
from django.urls import reverse, resolve, get_resolver
from django.conf import settings
from ventas.models import Comanda, VentaReserva, Producto
import sys


class Command(BaseCommand):
    help = 'Diagnóstico del sistema de comandas de clientes vía WhatsApp'

    def add_arguments(self, parser):
        parser.add_argument(
            'token',
            nargs='?',
            type=str,
            help='Token de comanda a diagnosticar (opcional)'
        )

    def handle(self, *args, **options):
        token = options.get('token')

        self.stdout.write(self.style.HTTP_INFO('='*80))
        self.stdout.write(self.style.HTTP_INFO('DIAGNÓSTICO: Sistema de Comandas de Clientes vía WhatsApp'))
        self.stdout.write(self.style.HTTP_INFO('='*80))
        self.stdout.write('')

        # 1. Verificar configuración
        self.stdout.write(self.style.WARNING('1. CONFIGURACIÓN'))
        self.stdout.write(self.style.WARNING('-' * 40))

        site_url = getattr(settings, 'SITE_URL', None)
        if site_url:
            self.stdout.write(self.style.SUCCESS(f'   ✓ SITE_URL configurada: {site_url}'))
        else:
            self.stdout.write(self.style.ERROR(f'   ✗ SITE_URL no está configurada'))

        flow_key = getattr(settings, 'FLOW_API_KEY', None)
        if flow_key and flow_key != 'YOUR_DEFAULT_API_KEY':
            self.stdout.write(self.style.SUCCESS(f'   ✓ FLOW_API_KEY configurada'))
        else:
            self.stdout.write(self.style.ERROR(f'   ✗ FLOW_API_KEY no está configurada'))

        self.stdout.write('')

        # 2. Verificar URLs registradas
        self.stdout.write(self.style.WARNING('2. URLs REGISTRADAS'))
        self.stdout.write(self.style.WARNING('-' * 40))

        url_patterns_to_check = [
            ('ventas:comanda_cliente', 'comanda_cliente_menu'),
            ('ventas:comanda_cliente_agregar_producto', 'agregar_producto'),
            ('ventas:comanda_cliente_actualizar_cantidad', 'actualizar_cantidad'),
            ('ventas:comanda_cliente_finalizar', 'finalizar'),
            ('ventas:comanda_cliente_pago_confirmacion', 'pago_confirmacion'),
            ('ventas:comanda_cliente_pago_retorno', 'pago_retorno'),
        ]

        for url_name, descripcion in url_patterns_to_check:
            try:
                test_url = reverse(url_name, kwargs={'token': 'test123'})
                self.stdout.write(self.style.SUCCESS(f'   ✓ {url_name}'))
                self.stdout.write(f'     Path: {test_url}')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ✗ {url_name}: {str(e)}'))

        self.stdout.write('')

        # 3. Verificar imports
        self.stdout.write(self.style.WARNING('3. MÓDULOS Y VISTAS'))
        self.stdout.write(self.style.WARNING('-' * 40))

        try:
            import ventas.views_comandas_cliente
            self.stdout.write(self.style.SUCCESS(f'   ✓ views_comandas_cliente importado correctamente'))

            # Verificar que las vistas existen
            vistas_requeridas = [
                'comanda_cliente_menu',
                'comanda_cliente_agregar_producto',
                'comanda_cliente_actualizar_cantidad',
                'comanda_cliente_finalizar',
                'comanda_cliente_pago_confirmacion',
                'comanda_cliente_pago_retorno'
            ]

            for vista in vistas_requeridas:
                if hasattr(ventas.views_comandas_cliente, vista):
                    self.stdout.write(self.style.SUCCESS(f'     ✓ {vista}'))
                else:
                    self.stdout.write(self.style.ERROR(f'     ✗ {vista} no encontrada'))

        except ImportError as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Error importando views_comandas_cliente: {str(e)}'))

        self.stdout.write('')

        # 4. Verificar servicios
        self.stdout.write(self.style.WARNING('4. SERVICIOS'))
        self.stdout.write(self.style.WARNING('-' * 40))

        try:
            from ventas.services.flow_service import FlowService
            self.stdout.write(self.style.SUCCESS(f'   ✓ FlowService importado correctamente'))

            flow_service = FlowService()
            self.stdout.write(f'     API URL: {flow_service.create_api_url}')

        except ImportError as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Error importando FlowService: {str(e)}'))

        self.stdout.write('')

        # 5. Estadísticas de comandas
        self.stdout.write(self.style.WARNING('5. ESTADÍSTICAS DE COMANDAS'))
        self.stdout.write(self.style.WARNING('-' * 40))

        total_comandas = Comanda.objects.count()
        comandas_con_token = Comanda.objects.filter(token_acceso__isnull=False).count()
        comandas_cliente = Comanda.objects.filter(creada_por_cliente=True).count()

        self.stdout.write(f'   Total comandas: {total_comandas}')
        self.stdout.write(f'   Con token: {comandas_con_token}')
        self.stdout.write(f'   Creadas por cliente: {comandas_cliente}')

        # Comandas con link válido
        comandas_validas = 0
        for comanda in Comanda.objects.filter(token_acceso__isnull=False):
            if comanda.es_link_valido():
                comandas_validas += 1

        self.stdout.write(f'   Con link válido: {comandas_validas}')

        self.stdout.write('')

        # 6. Productos disponibles
        self.stdout.write(self.style.WARNING('6. PRODUCTOS PARA COMANDAS'))
        self.stdout.write(self.style.WARNING('-' * 40))

        productos_disponibles = Producto.objects.filter(
            comanda_cliente=True
        ).count()

        self.stdout.write(f'   Productos habilitados: {productos_disponibles}')

        if productos_disponibles == 0:
            self.stdout.write(self.style.ERROR('   ⚠ ADVERTENCIA: No hay productos habilitados para comandas de clientes'))
            self.stdout.write('     Solución: Ve al admin de Productos y marca "comanda_cliente=True"')

        self.stdout.write('')

        # 7. Diagnóstico específico de token (si se proporcionó)
        if token:
            self.stdout.write(self.style.WARNING(f'7. DIAGNÓSTICO DEL TOKEN: {token[:20]}...'))
            self.stdout.write(self.style.WARNING('-' * 40))

            try:
                comanda = Comanda.objects.get(token_acceso=token)
                self.stdout.write(self.style.SUCCESS(f'   ✓ Comanda encontrada: #{comanda.id}'))
                self.stdout.write(f'     VentaReserva: #{comanda.venta_reserva.id if comanda.venta_reserva else "N/A"}')
                self.stdout.write(f'     Estado: {comanda.estado}')
                self.stdout.write(f'     Creada por cliente: {comanda.creada_por_cliente}')
                self.stdout.write(f'     Fecha vencimiento: {comanda.fecha_vencimiento_link}')

                if comanda.es_link_valido():
                    self.stdout.write(self.style.SUCCESS(f'     ✓ Link VÁLIDO'))
                else:
                    self.stdout.write(self.style.ERROR(f'     ✗ Link EXPIRADO'))

                # Intentar generar URL
                try:
                    url = comanda.obtener_url_cliente()
                    self.stdout.write(f'     URL: {url}')

                    # Intentar resolver la URL
                    path = url.replace(site_url, '') if site_url else url
                    try:
                        match = resolve(path)
                        self.stdout.write(self.style.SUCCESS(f'     ✓ URL resuelve correctamente'))
                        self.stdout.write(f'       View: {match.func.__name__}')
                        self.stdout.write(f'       Pattern: {match.url_name}')
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'     ✗ URL no resuelve: {str(e)}'))

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'     ✗ Error generando URL: {str(e)}'))

                # Verificar detalles de la comanda
                detalles = comanda.detalles.count()
                self.stdout.write(f'     Productos en comanda: {detalles}')

            except Comanda.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'   ✗ Comanda no encontrada con ese token'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ✗ Error: {str(e)}'))

            self.stdout.write('')

        # 8. Ejemplos de comandas recientes
        self.stdout.write(self.style.WARNING('8. ÚLTIMAS 5 COMANDAS CON TOKEN'))
        self.stdout.write(self.style.WARNING('-' * 40))

        comandas_recientes = Comanda.objects.filter(
            token_acceso__isnull=False
        ).order_by('-id')[:5]

        if comandas_recientes.exists():
            for comanda in comandas_recientes:
                valido = '✓' if comanda.es_link_valido() else '✗'
                self.stdout.write(f'   {valido} Comanda #{comanda.id} | Estado: {comanda.estado} | Token: {comanda.token_acceso[:20]}...')
        else:
            self.stdout.write('   (No hay comandas con token)')

        self.stdout.write('')

        # 9. Test de creación de URL
        self.stdout.write(self.style.WARNING('9. TEST DE GENERACIÓN DE URL'))
        self.stdout.write(self.style.WARNING('-' * 40))

        try:
            test_token = 'TEST_TOKEN_123'
            test_url = reverse('ventas:comanda_cliente', kwargs={'token': test_token})
            full_url = f"{site_url}{test_url}" if site_url else test_url
            self.stdout.write(self.style.SUCCESS(f'   ✓ URL de prueba generada correctamente'))
            self.stdout.write(f'     {full_url}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Error generando URL de prueba: {str(e)}'))

        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('='*80))
        self.stdout.write(self.style.HTTP_INFO('FIN DEL DIAGNÓSTICO'))
        self.stdout.write(self.style.HTTP_INFO('='*80))
        self.stdout.write('')

        # Recomendaciones finales
        self.stdout.write(self.style.WARNING('RECOMENDACIONES:'))
        self.stdout.write('1. Si las URLs no están registradas → Reiniciar servidor Django')
        self.stdout.write('2. Si SITE_URL falta → Agregar a settings.py o variables de entorno')
        self.stdout.write('3. Si no hay productos → Habilitar productos en admin con comanda_cliente=True')
        self.stdout.write('4. Si el token no existe → Generar nuevo link desde el admin de reservas')
        self.stdout.write('')
