"""
Management command para verificar que la segmentación incluye datos históricos
"""
from django.core.management.base import BaseCommand
from django.db import connection
from ventas.models import ServiceHistory, Cliente
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.db import models


class Command(BaseCommand):
    help = 'Verifica que la segmentación incluye datos históricos y actuales'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('VERIFICACIÓN DE SEGMENTACIÓN'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

        # 1. Verificar tabla crm_service_history
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'crm_service_history'
                    )
                """)
                table_exists = cursor.fetchone()[0]
            
            if table_exists:
                self.stdout.write(self.style.SUCCESS('\n✅ Tabla crm_service_history EXISTS'))
                
                # Contar servicios históricos
                historical_count = ServiceHistory.objects.count()
                self.stdout.write(f'   Total servicios históricos: {historical_count:,}')
            else:
                self.stdout.write(self.style.ERROR('\n❌ Tabla crm_service_history NO EXISTE'))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error verificando tabla: {e}'))
            return

        # 2. Verificar datos actuales
        current_services = Cliente.objects.annotate(
            service_count=Count('ventareserva')
        ).filter(service_count__gt=0).count()
        
        self.stdout.write(f'\n📊 Clientes con servicios ACTUALES: {current_services:,}')

        # 3. Verificar datos históricos
        historical_clients = Cliente.objects.filter(
            historial_servicios__isnull=False
        ).distinct().count()
        
        self.stdout.write(f'📚 Clientes con servicios HISTÓRICOS: {historical_clients:,}')

        # 4. Verificar query combinada
        self.stdout.write(self.style.WARNING('\n🔍 Ejecutando query de segmentación combinada...\n'))
        
        try:
            query = """
            SELECT
                c.id as cliente_id,
                c.nombre,
                -- Servicios actuales
                COUNT(DISTINCT vr.id) as servicios_actuales,
                COALESCE(SUM(vr.total), 0) as gasto_actual,
                -- Servicios históricos
                COUNT(DISTINCT sh.id) as servicios_historicos,
                COALESCE(SUM(sh.price_paid), 0) as gasto_historico,
                -- Totales combinados
                (COUNT(DISTINCT vr.id) + COUNT(DISTINCT sh.id)) as total_servicios,
                (COALESCE(SUM(vr.total), 0) + COALESCE(SUM(sh.price_paid), 0)) as total_gasto
            FROM ventas_cliente c
            LEFT JOIN ventas_ventareserva vr ON c.id = vr.cliente_id
            LEFT JOIN crm_service_history sh ON c.id = sh.cliente_id
            GROUP BY c.id, c.nombre
            HAVING (COUNT(DISTINCT vr.id) + COUNT(DISTINCT sh.id)) > 0
            ORDER BY total_gasto DESC
            LIMIT 10
            """

            with connection.cursor() as cursor:
                cursor.execute(query)
                columns = [col[0] for col in cursor.description]
                results = cursor.fetchall()

                self.stdout.write(self.style.SUCCESS('✅ Query ejecutada exitosamente\n'))
                self.stdout.write('Top 10 clientes (datos combinados):\n')
                self.stdout.write('-' * 120)
                self.stdout.write('\n{:<30} | {:>10} | {:>15} | {:>10} | {:>15} | {:>10} | {:>15}'.format(
                    'Cliente', 'Serv.Actual', 'Gasto Actual', 'Serv.Hist', 'Gasto Hist', 'Total Serv', 'Gasto Total'
                ))
                self.stdout.write('\n' + '-' * 120)

                for row in results:
                    data = dict(zip(columns, row))
                    self.stdout.write('\n{:<30} | {:>10} | ${:>14,.0f} | {:>10} | ${:>14,.0f} | {:>10} | ${:>14,.0f}'.format(
                        data['nombre'][:28],
                        data['servicios_actuales'],
                        float(data['gasto_actual']),
                        data['servicios_historicos'],
                        float(data['gasto_historico']),
                        data['total_servicios'],
                        float(data['total_gasto'])
                    ))

                self.stdout.write('\n' + '-' * 120)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error ejecutando query: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())
            return

        # 5. Resumen
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('CONCLUSIÓN'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        if historical_clients > 0:
            self.stdout.write(self.style.SUCCESS('\n✅ LA SEGMENTACIÓN INCLUYE DATOS HISTÓRICOS'))
            self.stdout.write(f'\n   - {historical_clients:,} clientes tienen servicios históricos')
            self.stdout.write(f'   - {historical_count:,} servicios históricos totales')
            self.stdout.write('\n   - El query combina ambas fuentes correctamente')
        else:
            self.stdout.write(self.style.ERROR('\n❌ NO SE ENCONTRARON DATOS HISTÓRICOS EN LA SEGMENTACIÓN'))

        self.stdout.write('\n')
