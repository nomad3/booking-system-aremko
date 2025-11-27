"""
Comando para diagnosticar por qué un cliente no aparece en el filtro personalizado
"""
from django.core.management.base import BaseCommand
from ventas.models import Cliente
from django.db.models import Sum, Count
from django.db.models.functions import Coalesce
from django.db import models, connection


class Command(BaseCommand):
    help = 'Diagnostica por qué un cliente no aparece en el filtro personalizado'

    def add_arguments(self, parser):
        parser.add_argument('--cliente-id', type=int, required=True, help='ID del cliente a diagnosticar')
        parser.add_argument('--gasto-min', type=float, default=0, help='Gasto mínimo del filtro')
        parser.add_argument('--gasto-max', type=float, default=None, help='Gasto máximo del filtro')

    def handle(self, *args, **options):
        cliente_id = options['cliente_id']
        gasto_min = options['gasto_min']
        gasto_max = options['gasto_max'] if options['gasto_max'] else float('inf')

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS(f'DIAGNÓSTICO DE CLIENTE #{cliente_id}'))
        self.stdout.write(self.style.SUCCESS('=' * 80))

        try:
            cliente = Cliente.objects.get(id=cliente_id)
        except Cliente.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Cliente #{cliente_id} no existe'))
            return

        # Información básica
        self.stdout.write(f'\n📋 Información Básica:')
        self.stdout.write(f'   Nombre: {cliente.nombre}')
        self.stdout.write(f'   Email: {cliente.email or "(VACÍO)"}')
        self.stdout.write(f'   Teléfono: {cliente.telefono or "(VACÍO)"}')
        self.stdout.write(f'   Comuna: {cliente.comuna.nombre if cliente.comuna else "(SIN COMUNA)"}')

        # Gasto actual (desde VentaReserva)
        gasto_actual = cliente.ventareserva_set.filter(
            estado_pago__in=['pagado', 'parcial']
        ).aggregate(
            total=Coalesce(Sum('total'), 0, output_field=models.DecimalField())
        )['total']

        self.stdout.write(f'\n💰 Gasto Actual (VentaReserva):')
        self.stdout.write(f'   Total: ${float(gasto_actual):,.0f}')

        # Gasto histórico (desde ServiceHistory)
        try:
            query_historico = """
            SELECT COALESCE(SUM(price_paid), 0) as total
            FROM crm_service_history
            WHERE cliente_id = %s
              AND service_date != '2021-01-01'
            """
            with connection.cursor() as cursor:
                cursor.execute(query_historico, [cliente_id])
                gasto_historico = cursor.fetchone()[0]

            self.stdout.write(f'\n📜 Gasto Histórico (ServiceHistory):')
            self.stdout.write(f'   Total: ${float(gasto_historico):,.0f}')
        except Exception as e:
            self.stdout.write(f'\n⚠️  No se pudo obtener gasto histórico: {e}')
            gasto_historico = 0

        # Gasto total combinado
        gasto_total = float(gasto_actual) + float(gasto_historico)
        self.stdout.write(f'\n💵 Gasto Total Combinado:')
        self.stdout.write(f'   Total: ${gasto_total:,.0f}')

        # Verificar si está en el rango del filtro
        self.stdout.write(f'\n🔍 Verificación de Filtro:')
        self.stdout.write(f'   Rango solicitado: ${gasto_min:,.0f} - ${gasto_max:,.0f}')
        
        if gasto_min <= gasto_total <= gasto_max:
            self.stdout.write(self.style.SUCCESS(f'   ✅ El cliente ESTÁ en el rango de gasto'))
        else:
            self.stdout.write(self.style.ERROR(f'   ❌ El cliente NO está en el rango de gasto'))

        # Verificar agrupación por teléfono
        if cliente.telefono:
            self.stdout.write(f'\n📞 Agrupación por Teléfono:')
            clientes_mismo_telefono = Cliente.objects.filter(telefono=cliente.telefono)
            self.stdout.write(f'   Clientes con mismo teléfono ({cliente.telefono}): {clientes_mismo_telefono.count()}')
            
            if clientes_mismo_telefono.count() > 1:
                self.stdout.write(f'   ⚠️  MÚLTIPLES CLIENTES CON MISMO TELÉFONO:')
                for c in clientes_mismo_telefono:
                    self.stdout.write(f'      - ID {c.id}: {c.nombre} ({c.email or "sin email"})')
                
                # ID representante (el mínimo)
                id_representante = clientes_mismo_telefono.order_by('id').first().id
                self.stdout.write(f'   ID Representante (mínimo): {id_representante}')
                
                if id_representante != cliente_id:
                    self.stdout.write(self.style.WARNING(
                        f'   ⚠️  Este cliente NO es el representante. '
                        f'Sus gastos se suman al cliente #{id_representante}'
                    ))
        else:
            self.stdout.write(self.style.ERROR(f'\n❌ PROBLEMA: El cliente NO tiene teléfono'))
            self.stdout.write(f'   El query de segmentación EXCLUYE clientes sin teléfono')
            self.stdout.write(f'   Esto explica por qué no aparece en el filtro')

        # Verificar filtro de email
        self.stdout.write(f'\n📧 Verificación de Email:')
        if cliente.email and cliente.email.strip():
            self.stdout.write(f'   ✅ Tiene email: {cliente.email}')
        else:
            self.stdout.write(f'   ❌ NO tiene email (filtro "con_email" lo excluiría)')

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('FIN DEL DIAGNÓSTICO'))
        self.stdout.write('=' * 80 + '\n')
