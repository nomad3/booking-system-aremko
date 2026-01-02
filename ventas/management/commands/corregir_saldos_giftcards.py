"""
Comando de Django management para corregir automáticamente los saldos de GiftCards.

EJECUCIÓN EN RENDER:
python manage.py corregir_saldos_giftcards

MODO DRY-RUN (solo mostrar cambios sin aplicarlos):
python manage.py corregir_saldos_giftcards --dry-run

CORREGIR GIFTCARD ESPECÍFICA:
python manage.py corregir_saldos_giftcards --codigo ZADH3G6D3MZT
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from decimal import Decimal
from ventas.models import GiftCard, Pago


class Command(BaseCommand):
    help = 'Corrige automáticamente los saldos inconsistentes de GiftCards'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Modo simulación: muestra cambios sin aplicarlos',
        )
        parser.add_argument(
            '--codigo',
            type=str,
            help='Código de GiftCard específica a corregir',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        codigo_especifico = options.get('codigo')

        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("  CORRECCIÓN DE SALDOS DE GIFTCARDS"))
        if dry_run:
            self.stdout.write(self.style.WARNING("  MODO DRY-RUN (Simulación)"))
        self.stdout.write("=" * 80 + "\n")

        # Obtener GiftCards a procesar
        if codigo_especifico:
            try:
                giftcards = [GiftCard.objects.get(codigo=codigo_especifico)]
                self.stdout.write(f"Procesando GiftCard específica: {codigo_especifico}\n")
            except GiftCard.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ GiftCard con código {codigo_especifico} no encontrada"))
                return
        else:
            # Obtener todas las GiftCards que han sido usadas
            giftcards = GiftCard.objects.filter(pago__isnull=False).distinct()
            self.stdout.write(f"Analizando {giftcards.count()} GiftCards...\n")

        correcciones_aplicadas = 0
        errores = 0

        for gc in giftcards:
            try:
                # Calcular total usado en pagos
                total_usado = Pago.objects.filter(
                    giftcard=gc,
                    metodo_pago='giftcard'
                ).aggregate(
                    total=Sum('monto')
                )['total'] or Decimal('0')

                # Calcular saldo esperado
                saldo_esperado = gc.monto_inicial - total_usado

                # Verificar si hay inconsistencia
                if gc.monto_disponible != saldo_esperado:
                    self.stdout.write(f"\n📝 GiftCard: {gc.codigo}")
                    self.stdout.write(f"   Monto inicial: ${gc.monto_inicial:,.0f}")
                    self.stdout.write(f"   Total usado en pagos: ${total_usado:,.0f}")
                    self.stdout.write(self.style.ERROR(
                        f"   Saldo actual (INCORRECTO): ${gc.monto_disponible:,.0f}"
                    ))
                    self.stdout.write(self.style.SUCCESS(
                        f"   Saldo esperado (CORRECTO): ${saldo_esperado:,.0f}"
                    ))

                    # Calcular cambios
                    diferencia = gc.monto_disponible - saldo_esperado
                    self.stdout.write(self.style.WARNING(
                        f"   Diferencia: ${diferencia:,.0f}"
                    ))

                    # Determinar nuevo estado
                    nuevo_estado = 'cobrado' if saldo_esperado == 0 else 'por_cobrar'
                    cambio_estado = gc.estado != nuevo_estado

                    if cambio_estado:
                        self.stdout.write(f"   Estado actual: {gc.estado}")
                        self.stdout.write(f"   Nuevo estado: {nuevo_estado}")

                    # Aplicar corrección si no es dry-run
                    if not dry_run:
                        with transaction.atomic():
                            gc.monto_disponible = saldo_esperado
                            gc.estado = nuevo_estado
                            gc.save()

                        self.stdout.write(self.style.SUCCESS("   ✓ CORREGIDO"))
                        correcciones_aplicadas += 1
                    else:
                        self.stdout.write(self.style.WARNING("   → Se corregiría (dry-run)"))
                        correcciones_aplicadas += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"\n❌ ERROR procesando GiftCard {gc.codigo}: {str(e)}"
                ))
                errores += 1
                continue

        # Resumen final
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("  RESUMEN")
        self.stdout.write("=" * 80 + "\n")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"GiftCards que SERÍAN corregidas: {correcciones_aplicadas}"
            ))
            if correcciones_aplicadas > 0:
                self.stdout.write(self.style.WARNING(
                    "\n💡 Ejecuta sin --dry-run para aplicar las correcciones"
                ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"✓ GiftCards corregidas: {correcciones_aplicadas}"
            ))

        if errores > 0:
            self.stdout.write(self.style.ERROR(
                f"❌ Errores encontrados: {errores}"
            ))

        if correcciones_aplicadas == 0 and errores == 0:
            self.stdout.write(self.style.SUCCESS(
                "✓ No se encontraron inconsistencias. Todas las GiftCards están correctas."
            ))
