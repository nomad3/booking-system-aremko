# -*- coding: utf-8 -*-
"""
Management command para diagnosticar errores en el sistema de pagos a masajistas
"""

from django.core.management.base import BaseCommand
from ventas.models import Proveedor, ReservaServicio
from decimal import Decimal
import traceback


class Command(BaseCommand):
    help = 'Diagnostica problemas en el sistema de pagos a masajistas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--masajista-id',
            type=int,
            default=3,
            help='ID del masajista a diagnosticar (default: 3)'
        )

    def handle(self, *args, **options):
        masajista_id = options['masajista_id']

        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("DIAGNÓSTICO DE ERROR EN PAGOS A MASAJISTAS"))
        self.stdout.write("=" * 80)

        self.stdout.write(f"\n1. Verificando que el proveedor ID={masajista_id} existe...")
        try:
            masajista = Proveedor.objects.get(id=masajista_id)
            self.stdout.write(self.style.SUCCESS(f"✅ Proveedor encontrado: {masajista.nombre}"))
        except Proveedor.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ ERROR: No existe proveedor con ID={masajista_id}"))
            return

        self.stdout.write(f"\n2. Información del proveedor:")
        self.stdout.write(f"   - ID: {masajista.id}")
        self.stdout.write(f"   - Nombre: {masajista.nombre}")
        self.stdout.write(f"   - Email: {masajista.email}")
        self.stdout.write(f"   - Teléfono: {masajista.telefono}")
        self.stdout.write(f"   - Es masajista: {masajista.es_masajista}")
        self.stdout.write(f"   - Porcentaje comisión: {masajista.porcentaje_comision}%")
        self.stdout.write(f"   - RUT: {masajista.rut}")
        self.stdout.write(f"   - Banco: {masajista.banco}")
        self.stdout.write(f"   - Tipo cuenta: {masajista.tipo_cuenta}")
        self.stdout.write(f"   - Número cuenta: {masajista.numero_cuenta}")

        self.stdout.write(f"\n3. Verificando método get_servicios_pendientes_pago()...")
        try:
            servicios = masajista.get_servicios_pendientes_pago()
            self.stdout.write(self.style.SUCCESS(f"✅ Método ejecutado correctamente"))
            self.stdout.write(f"   - Servicios pendientes: {servicios.count()}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ ERROR al ejecutar get_servicios_pendientes_pago():"))
            self.stdout.write(self.style.ERROR(f"   {type(e).__name__}: {str(e)}"))
            self.stdout.write(traceback.format_exc())
            return

        self.stdout.write(f"\n4. Intentando optimizar con select_related...")
        try:
            servicios_optimizados = masajista.get_servicios_pendientes_pago().select_related(
                'servicio',
                'venta_reserva',
                'venta_reserva__cliente'
            )
            self.stdout.write(self.style.SUCCESS(f"✅ Query optimizado correctamente"))
            self.stdout.write(f"   - Servicios con select_related: {servicios_optimizados.count()}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ ERROR al optimizar query:"))
            self.stdout.write(self.style.ERROR(f"   {type(e).__name__}: {str(e)}"))
            self.stdout.write(traceback.format_exc())
            return

        self.stdout.write(f"\n5. Procesando cada servicio (simulando la vista)...")
        try:
            servicios_con_montos = []
            total_bruto = Decimal('0')
            total_neto = Decimal('0')

            # Procesar solo los primeros 5 servicios para diagnóstico
            for i, servicio in enumerate(servicios_optimizados[:5], 1):
                self.stdout.write(f"\n   Servicio {i}:")
                self.stdout.write(f"   - ID: {servicio.id}")
                self.stdout.write(f"   - Servicio: {servicio.servicio.nombre}")
                self.stdout.write(f"   - Fecha: {servicio.fecha_agendamiento}")

                try:
                    precio_servicio = servicio.calcular_precio()
                    self.stdout.write(f"   - Precio calculado: ${precio_servicio:,.0f}")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ ERROR al calcular precio: {e}"))
                    self.stdout.write(traceback.format_exc())
                    continue

                try:
                    monto_masajista = precio_servicio * (masajista.porcentaje_comision / 100)
                    self.stdout.write(f"   - Monto masajista: ${monto_masajista:,.0f}")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ ERROR al calcular monto masajista: {e}"))
                    self.stdout.write(traceback.format_exc())
                    continue

                try:
                    monto_retencion = monto_masajista * Decimal('0.145')
                    monto_neto = monto_masajista - monto_retencion
                    self.stdout.write(f"   - Retención: ${monto_retencion:,.0f}")
                    self.stdout.write(f"   - Monto neto: ${monto_neto:,.0f}")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ ERROR al calcular retención: {e}"))
                    self.stdout.write(traceback.format_exc())
                    continue

                try:
                    cliente = servicio.venta_reserva.cliente
                    self.stdout.write(f"   - Cliente: {cliente.nombre}")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ ERROR al obtener cliente: {e}"))
                    self.stdout.write(traceback.format_exc())
                    continue

                servicios_con_montos.append({
                    'servicio': servicio,
                    'precio_servicio': precio_servicio,
                    'monto_masajista': monto_masajista,
                    'monto_neto': monto_neto,
                })

                total_bruto += monto_masajista
                total_neto += monto_neto

            self.stdout.write(self.style.SUCCESS(f"\n   ✅ Procesados {len(servicios_con_montos)} servicios exitosamente"))
            self.stdout.write(f"   - Total bruto: ${total_bruto:,.0f}")
            self.stdout.write(f"   - Total neto: ${total_neto:,.0f}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ ERROR durante el procesamiento:"))
            self.stdout.write(self.style.ERROR(f"   {type(e).__name__}: {str(e)}"))
            self.stdout.write(traceback.format_exc())
            return

        self.stdout.write(f"\n6. Verificando atributos necesarios para el template...")
        try:
            context = {
                'masajista': masajista,
                'servicios': servicios_con_montos,
                'total_bruto': total_bruto,
                'total_retencion': total_bruto * Decimal('0.145'),
                'total_neto': total_neto,
            }
            self.stdout.write(self.style.SUCCESS(f"✅ Contexto creado correctamente:"))
            self.stdout.write(f"   - Masajista: {context['masajista']}")
            self.stdout.write(f"   - Servicios: {len(context['servicios'])} items")
            self.stdout.write(f"   - Total bruto: ${context['total_bruto']:,.0f}")
            self.stdout.write(f"   - Total retención: ${context['total_retencion']:,.0f}")
            self.stdout.write(f"   - Total neto: ${context['total_neto']:,.0f}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ ERROR al crear contexto:"))
            self.stdout.write(self.style.ERROR(f"   {type(e).__name__}: {str(e)}"))
            self.stdout.write(traceback.format_exc())
            return

        self.stdout.write(f"\n7. Verificando relación reservas_asignadas (related_name)...")
        try:
            reservas = masajista.reservas_asignadas.all()
            self.stdout.write(self.style.SUCCESS(f"✅ Related name 'reservas_asignadas' funciona correctamente"))
            self.stdout.write(f"   - Total reservas asignadas: {reservas.count()}")
        except AttributeError as e:
            self.stdout.write(self.style.ERROR(f"❌ ERROR: El related_name 'reservas_asignadas' no existe"))
            self.stdout.write(self.style.ERROR(f"   {str(e)}"))
            self.stdout.write(traceback.format_exc())
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ ERROR al acceder a reservas_asignadas:"))
            self.stdout.write(self.style.ERROR(f"   {type(e).__name__}: {str(e)}"))
            self.stdout.write(traceback.format_exc())

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("DIAGNÓSTICO COMPLETADO"))
        self.stdout.write("=" * 80)
        self.stdout.write("\nSi todos los pasos anteriores pasaron ✅, el problema podría estar en:")
        self.stdout.write("1. El template registrar_pago.html (error de sintaxis)")
        self.stdout.write("2. Middleware o decoradores que interfieren")
        self.stdout.write("3. Configuración de URLs")
        self.stdout.write("4. Problemas de permisos de usuario")
        self.stdout.write("\nSi algún paso falló ❌, el error está en el modelo o la lógica de negocio.")
