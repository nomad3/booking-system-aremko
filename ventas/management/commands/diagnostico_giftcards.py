"""
Comando de Django management para diagnosticar problemas con GiftCards.

EJECUCIÓN EN RENDER:
python manage.py diagnostico_giftcards

EJECUCIÓN CON RESERVA ESPECÍFICA:
python manage.py diagnostico_giftcards --reserva 4388
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from ventas.models import GiftCard, Pago, VentaReserva, Cliente


class Command(BaseCommand):
    help = 'Diagnóstico completo de GiftCards para identificar inconsistencias'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reserva',
            type=int,
            help='ID de la reserva específica a analizar (ej: 4388)',
        )
        parser.add_argument(
            '--prueba',
            action='store_true',
            help='Ejecutar prueba de creación de GiftCard',
        )

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("  DIAGNÓSTICO DE GIFTCARDS - SISTEMA AREMKO"))
        self.stdout.write("=" * 80 + "\n")

        # Si se especificó una reserva, analizarla
        if options['reserva']:
            self.analizar_reserva_especifica(options['reserva'])
        else:
            # Buscar todas las GiftCards con posibles inconsistencias
            self.buscar_inconsistencias_globales()

        # Si se solicitó prueba, ejecutarla
        if options['prueba']:
            self.ejecutar_prueba_giftcard()

    def analizar_reserva_especifica(self, reserva_id):
        """Analiza una reserva específica y su GiftCard"""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(f"  ANÁLISIS DE RESERVA #{reserva_id}")
        self.stdout.write("=" * 80 + "\n")

        try:
            reserva = VentaReserva.objects.get(id=reserva_id)
            self.stdout.write(self.style.SUCCESS(f"✓ Reserva encontrada: #{reserva.id}"))
            self.stdout.write(f"  Cliente: {reserva.cliente.nombre}")
            self.stdout.write(f"  Total reserva: ${reserva.total:,.0f}")
            self.stdout.write(f"  Estado pago: {reserva.estado_pago}\n")

            # Buscar pagos de la reserva
            pagos = reserva.pagos.all()
            self.stdout.write(f"Pagos registrados: {pagos.count()}\n")

            giftcard_encontrada = None
            for pago in pagos:
                self.stdout.write(f"  Pago ID: {pago.id}")
                self.stdout.write(f"  - Método: {pago.metodo_pago}")
                self.stdout.write(f"  - Monto: ${pago.monto:,.0f}")
                self.stdout.write(f"  - Fecha: {pago.fecha_pago}")

                if pago.metodo_pago == 'giftcard' and pago.giftcard:
                    gc = pago.giftcard
                    self.stdout.write(f"  - GiftCard asociada: {gc.codigo}")
                    self.stdout.write(f"    * Monto inicial: ${gc.monto_inicial:,.0f}")
                    self.stdout.write(f"    * Monto disponible: ${gc.monto_disponible:,.0f}")
                    self.stdout.write(f"    * Estado: {gc.estado}")

                    # Calcular saldo esperado
                    saldo_esperado = gc.monto_inicial - pago.monto
                    if gc.monto_disponible != saldo_esperado:
                        self.stdout.write(self.style.ERROR(
                            f"    * ⚠️ INCONSISTENCIA DETECTADA:"
                        ))
                        self.stdout.write(self.style.ERROR(
                            f"      Se pagó ${pago.monto:,.0f} pero el saldo es ${gc.monto_disponible:,.0f}"
                        ))
                        self.stdout.write(self.style.WARNING(
                            f"      Saldo esperado: ${saldo_esperado:,.0f}"
                        ))
                        self.stdout.write(self.style.WARNING(
                            f"      Diferencia: ${gc.monto_disponible - saldo_esperado:,.0f}"
                        ))
                    else:
                        self.stdout.write(self.style.SUCCESS("    * ✓ Saldo correcto"))

                    giftcard_encontrada = gc

                self.stdout.write("")

            # Si encontramos GiftCard, analizar todos sus usos
            if giftcard_encontrada:
                self.analizar_todos_usos_giftcard(giftcard_encontrada)

        except VentaReserva.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Reserva #{reserva_id} no encontrada"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ ERROR: {str(e)}"))
            import traceback
            traceback.print_exc()

    def analizar_todos_usos_giftcard(self, giftcard):
        """Analiza todos los pagos realizados con una GiftCard"""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(f"  ANÁLISIS COMPLETO DE GIFTCARD {giftcard.codigo}")
        self.stdout.write("=" * 80 + "\n")

        pagos = Pago.objects.filter(giftcard=giftcard).order_by('fecha_pago')
        self.stdout.write(f"Total de pagos con esta GiftCard: {pagos.count()}\n")

        monto_total_usado = Decimal('0')
        for i, pago in enumerate(pagos, 1):
            self.stdout.write(f"{i}. Pago ID: {pago.id}")
            self.stdout.write(f"   Reserva: #{pago.venta_reserva.id}")
            self.stdout.write(f"   Monto: ${pago.monto:,.0f}")
            self.stdout.write(f"   Fecha: {pago.fecha_pago}")
            monto_total_usado += pago.monto
            self.stdout.write("")

        self.stdout.write("RESUMEN:")
        self.stdout.write(f"  Monto inicial GiftCard: ${giftcard.monto_inicial:,.0f}")
        self.stdout.write(f"  Total usado en pagos: ${monto_total_usado:,.0f}")
        self.stdout.write(f"  Saldo actual en GiftCard: ${giftcard.monto_disponible:,.0f}")

        saldo_esperado = giftcard.monto_inicial - monto_total_usado
        self.stdout.write(f"  Saldo esperado: ${saldo_esperado:,.0f}")

        diferencia = giftcard.monto_disponible - saldo_esperado
        if diferencia != 0:
            self.stdout.write(self.style.ERROR(
                f"\n⚠️ INCONSISTENCIA: Diferencia de ${diferencia:,.0f}"
            ))
            self.stdout.write(self.style.WARNING(
                "\nPROPUESTA DE CORRECCIÓN:"
            ))
            self.stdout.write(f"  1. Actualizar monto_disponible de ${giftcard.monto_disponible:,.0f} a ${saldo_esperado:,.0f}")
            if saldo_esperado == 0:
                self.stdout.write(f"  2. Cambiar estado de '{giftcard.estado}' a 'cobrado'")
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ GiftCard consistente"))

    def buscar_inconsistencias_globales(self):
        """Busca todas las GiftCards con posibles inconsistencias"""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("  BÚSQUEDA GLOBAL DE INCONSISTENCIAS")
        self.stdout.write("=" * 80 + "\n")

        # Obtener todas las GiftCards que han sido usadas
        giftcards_usadas = GiftCard.objects.filter(
            pago__isnull=False
        ).distinct()

        self.stdout.write(f"Analizando {giftcards_usadas.count()} GiftCards que han sido usadas en pagos...\n")

        inconsistencias_encontradas = []

        for gc in giftcards_usadas:
            # Calcular total usado
            total_usado = Pago.objects.filter(
                giftcard=gc,
                metodo_pago='giftcard'
            ).aggregate(total=Decimal('0'))['total'] or Decimal('0')

            saldo_esperado = gc.monto_inicial - total_usado
            diferencia = gc.monto_disponible - saldo_esperado

            if diferencia != 0:
                inconsistencias_encontradas.append({
                    'giftcard': gc,
                    'total_usado': total_usado,
                    'saldo_actual': gc.monto_disponible,
                    'saldo_esperado': saldo_esperado,
                    'diferencia': diferencia
                })

        if inconsistencias_encontradas:
            self.stdout.write(self.style.ERROR(
                f"⚠️ Se encontraron {len(inconsistencias_encontradas)} GiftCards con inconsistencias:\n"
            ))

            for item in inconsistencias_encontradas:
                gc = item['giftcard']
                self.stdout.write(f"GiftCard: {gc.codigo}")
                self.stdout.write(f"  Monto inicial: ${gc.monto_inicial:,.0f}")
                self.stdout.write(f"  Total usado en pagos: ${item['total_usado']:,.0f}")
                self.stdout.write(f"  Saldo actual: ${item['saldo_actual']:,.0f}")
                self.stdout.write(self.style.WARNING(
                    f"  Saldo esperado: ${item['saldo_esperado']:,.0f}"
                ))
                self.stdout.write(self.style.ERROR(
                    f"  Diferencia: ${item['diferencia']:,.0f}"
                ))
                self.stdout.write("")

            self.stdout.write(self.style.WARNING(
                "\n💡 RECOMENDACIÓN: Ejecutar script de corrección automática"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "✓ No se encontraron inconsistencias en las GiftCards"
            ))

    def ejecutar_prueba_giftcard(self):
        """Crea una GiftCard de prueba y verifica que el descuento funcione"""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("  PRUEBA DE FUNCIONALIDAD")
        self.stdout.write("=" * 80 + "\n")

        try:
            # Buscar o crear cliente de prueba
            cliente_prueba, created = Cliente.objects.get_or_create(
                telefono='+56900000000',
                defaults={
                    'nombre': 'Cliente Prueba GiftCard',
                    'email': 'prueba_giftcard@test.com'
                }
            )
            self.stdout.write(f"Cliente de prueba: {cliente_prueba.nombre}")

            # Crear GiftCard de prueba
            giftcard_prueba = GiftCard.objects.create(
                monto_inicial=50000,
                fecha_vencimiento=timezone.now().date() + timedelta(days=365),
                cliente_destinatario=cliente_prueba
            )
            self.stdout.write(self.style.SUCCESS(f"\n✓ GiftCard creada: {giftcard_prueba.codigo}"))
            self.stdout.write(f"  Monto inicial: ${giftcard_prueba.monto_inicial:,.0f}")
            self.stdout.write(f"  Monto disponible: ${giftcard_prueba.monto_disponible:,.0f}")

            # Crear reserva de prueba
            reserva_prueba = VentaReserva.objects.create(
                cliente=cliente_prueba,
                total=50000
            )
            self.stdout.write(self.style.SUCCESS(f"\n✓ Reserva de prueba creada: #{reserva_prueba.id}"))

            # Crear pago con GiftCard
            self.stdout.write(f"\n→ Creando pago de $30,000 con GiftCard...")
            pago_prueba = Pago(
                venta_reserva=reserva_prueba,
                monto=30000,
                metodo_pago='giftcard',
                giftcard=giftcard_prueba
            )
            pago_prueba.save()

            self.stdout.write(self.style.SUCCESS(f"✓ Pago creado: ID {pago_prueba.id}"))

            # Refrescar GiftCard
            giftcard_prueba.refresh_from_db()

            self.stdout.write(f"\n📊 RESULTADO:")
            self.stdout.write(f"  Monto disponible: ${giftcard_prueba.monto_disponible:,.0f}")
            self.stdout.write(f"  Estado: {giftcard_prueba.estado}")

            if giftcard_prueba.monto_disponible == 20000:
                self.stdout.write(self.style.SUCCESS(
                    "\n✓ ¡PRUEBA EXITOSA! El método save() funciona correctamente"
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f"\n❌ PRUEBA FALLIDA: Saldo esperado $20,000 pero es ${giftcard_prueba.monto_disponible:,.0f}"
                ))

            # Limpiar
            self.stdout.write(f"\n→ Limpiando datos de prueba...")
            pago_prueba.delete()
            reserva_prueba.delete()
            giftcard_prueba.delete()
            if created:
                cliente_prueba.delete()
            self.stdout.write(self.style.SUCCESS("✓ Datos de prueba eliminados"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ ERROR en prueba: {str(e)}"))
            import traceback
            traceback.print_exc()
