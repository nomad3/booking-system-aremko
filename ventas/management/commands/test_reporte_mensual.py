"""
Management command para diagnosticar problemas en el reporte mensual de masajistas
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from dateutil.relativedelta import relativedelta
import traceback

from ventas.models import Proveedor, ReservaServicio


class Command(BaseCommand):
    help = 'Diagnostica problemas en el reporte mensual de masajistas'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== DIAGNÓSTICO REPORTE MENSUAL MASAJISTAS ===\n'))

        try:
            # Test 1: Import de relativedelta
            self.stdout.write('Test 1: Import de relativedelta... ')
            from dateutil.relativedelta import relativedelta
            self.stdout.write(self.style.SUCCESS('✓ OK\n'))

            # Test 2: Obtener fecha actual
            self.stdout.write('Test 2: Obtener fecha actual... ')
            hoy = timezone.now().date()
            self.stdout.write(self.style.SUCCESS(f'✓ OK - Hoy: {hoy}\n'))

            # Test 3: Calcular rango de meses
            self.stdout.write('Test 3: Calcular rango de últimos 6 meses... ')
            fecha_fin = hoy.replace(day=1)
            fecha_inicio = fecha_fin - relativedelta(months=5)
            self.stdout.write(self.style.SUCCESS(f'✓ OK - Desde: {fecha_inicio}, Hasta: {fecha_fin}\n'))

            # Test 4: Generar lista de meses
            self.stdout.write('Test 4: Generar lista de meses... ')
            meses = []
            mes_actual = fecha_inicio
            while mes_actual <= fecha_fin:
                meses.append({
                    'fecha': mes_actual,
                    'nombre': mes_actual.strftime('%b %Y'),
                    'mes': mes_actual.month,
                    'anio': mes_actual.year
                })
                mes_actual += relativedelta(months=1)
            self.stdout.write(self.style.SUCCESS(f'✓ OK - {len(meses)} meses generados\n'))

            # Test 5: Obtener masajistas
            self.stdout.write('Test 5: Obtener masajistas... ')
            masajistas = Proveedor.objects.filter(
                es_masajista=True
            ).order_by('nombre')
            self.stdout.write(self.style.SUCCESS(f'✓ OK - {masajistas.count()} masajistas encontradas\n'))

            if masajistas.count() == 0:
                self.stdout.write(self.style.WARNING('⚠ No hay masajistas activas en el sistema\n'))
                return

            # Test 6: Procesar cada masajista
            self.stdout.write('\nTest 6: Procesar datos de masajistas...\n')
            datos_reporte = []

            for masajista in masajistas:
                self.stdout.write(f'\n  Procesando: {masajista.nombre}')
                self.stdout.write(f' (ID: {masajista.id}, Comisión: {masajista.porcentaje_comision}%)')

                fila = {
                    'masajista_id': masajista.id,
                    'masajista_nombre': masajista.nombre,
                    'porcentaje_comision': masajista.porcentaje_comision,
                    'meses': [],
                    'total_cobrado': Decimal('0'),
                    'total_comision': Decimal('0')
                }

                for mes in meses:
                    # Calcular fecha inicio y fin del mes
                    primer_dia = mes['fecha']
                    if mes['fecha'].month == 12:
                        ultimo_dia = mes['fecha'].replace(year=mes['fecha'].year + 1, month=1, day=1) - timedelta(days=1)
                    else:
                        ultimo_dia = mes['fecha'].replace(month=mes['fecha'].month + 1, day=1) - timedelta(days=1)

                    # Obtener reservas de este masajista en este mes, solo pagadas
                    try:
                        reservas = ReservaServicio.objects.filter(
                            proveedor_asignado=masajista,
                            fecha_agendamiento__gte=primer_dia,
                            fecha_agendamiento__lte=ultimo_dia,
                            venta_reserva__estado_pago='pagado'
                        ).select_related('servicio', 'venta_reserva', 'venta_reserva__cliente')

                        # Calcular totales del mes
                        total_mes_cobrado = Decimal('0')
                        total_mes_comision = Decimal('0')
                        cantidad_servicios = reservas.count()

                        for reserva in reservas:
                            # Validar que la reserva tenga servicio
                            if not reserva.servicio:
                                self.stdout.write(self.style.WARNING(f'\n    ⚠ Reserva {reserva.id} sin servicio asociado'))
                                continue

                            try:
                                # Total cobrado = precio del servicio * cantidad de personas
                                monto_cobrado = Decimal(str(reserva.servicio.precio_base)) * reserva.cantidad_personas

                                # Comisión = monto cobrado * (porcentaje / 100) SIN descontar impuestos
                                comision = monto_cobrado * (Decimal(str(masajista.porcentaje_comision)) / 100)

                                total_mes_cobrado += monto_cobrado
                                total_mes_comision += comision
                            except (AttributeError, TypeError, ValueError) as e:
                                self.stdout.write(self.style.ERROR(f'\n    ✗ Error en reserva {reserva.id}: {e}'))
                                continue

                        if cantidad_servicios > 0:
                            self.stdout.write(f'\n    {mes["nombre"]}: {cantidad_servicios} servicios, ${total_mes_cobrado}')

                        fila['meses'].append({
                            'mes': mes['mes'],
                            'anio': mes['anio'],
                            'nombre': mes['nombre'],
                            'total_cobrado': total_mes_cobrado,
                            'total_comision': total_mes_comision,
                            'cantidad_servicios': cantidad_servicios
                        })

                        fila['total_cobrado'] += total_mes_cobrado
                        fila['total_comision'] += total_mes_comision

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'\n    ✗ Error procesando mes {mes["nombre"]}: {e}'))
                        traceback.print_exc()

                datos_reporte.append(fila)
                self.stdout.write(self.style.SUCCESS(f'\n  ✓ Total: ${fila["total_cobrado"]}\n'))

            # Test 7: Calcular totales por mes
            self.stdout.write('\nTest 7: Calcular totales por mes... ')
            totales_mes = []
            for i, mes in enumerate(meses):
                total_mes_cobrado = Decimal('0')
                total_mes_comision = Decimal('0')
                for fila in datos_reporte:
                    if i < len(fila['meses']):
                        total_mes_cobrado += fila['meses'][i]['total_cobrado']
                        total_mes_comision += fila['meses'][i]['total_comision']
                totales_mes.append({
                    'total_cobrado': total_mes_cobrado,
                    'total_comision': total_mes_comision
                })
            self.stdout.write(self.style.SUCCESS('✓ OK\n'))

            # Test 8: Calcular gran total
            self.stdout.write('Test 8: Calcular gran total... ')
            gran_total_cobrado = sum(fila['total_cobrado'] for fila in datos_reporte)
            gran_total_comision = sum(fila['total_comision'] for fila in datos_reporte)
            self.stdout.write(self.style.SUCCESS(f'✓ OK - Total: ${gran_total_cobrado}\n'))

            # Resumen final
            self.stdout.write(self.style.SUCCESS('\n=== RESUMEN ==='))
            self.stdout.write(f'\nMasajistas procesadas: {len(datos_reporte)}')
            self.stdout.write(f'\nMeses procesados: {len(meses)}')
            self.stdout.write(f'\nTotal cobrado: ${gran_total_cobrado}')
            self.stdout.write(f'\nTotal comisión: ${gran_total_comision}')

            self.stdout.write(self.style.SUCCESS('\n\n✓ DIAGNÓSTICO COMPLETADO SIN ERRORES\n'))
            self.stdout.write('El reporte debería funcionar correctamente.\n')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n\n✗ ERROR CRÍTICO: {e}\n'))
            self.stdout.write(self.style.ERROR('\nTraceback completo:\n'))
            traceback.print_exc()
            self.stdout.write(self.style.ERROR('\n\nEste es el error que está causando el fallo en la web.\n'))
