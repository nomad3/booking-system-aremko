"""
Script de diagnóstico para analizar el problema de GiftCards no descontando saldo
al usarse como método de pago.

PROBLEMA REPORTADO:
- GiftCard se usó como pago por $150,000 en reserva 4388
- El saldo de la GiftCard sigue siendo $150,000 cuando debería ser $0

Este script analiza:
1. Estado actual de la GiftCard problemática
2. Pagos asociados a esa GiftCard
3. Prueba de creación y uso de GiftCard de prueba
4. Identificación de la causa del problema

EJECUCIÓN:
python3 manage.py shell < diagnostico_giftcards.py
"""

import os
import django
import sys

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'booking_system.settings')
django.setup()

from ventas.models import GiftCard, Pago, VentaReserva, Cliente
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


def separador(titulo):
    """Imprime un separador visual"""
    print("\n" + "=" * 80)
    print(f"  {titulo}")
    print("=" * 80 + "\n")


def analizar_giftcard_problematica():
    """Analiza la GiftCard que se reportó con problemas (reserva 4388)"""
    separador("ANÁLISIS DE GIFTCARD PROBLEMÁTICA - RESERVA 4388")

    try:
        reserva = VentaReserva.objects.get(id=4388)
        print(f"✓ Reserva encontrada: #{reserva.id}")
        print(f"  Cliente: {reserva.cliente.nombre}")
        print(f"  Total reserva: ${reserva.total:,.0f}")
        print(f"  Estado pago: {reserva.estado_pago}")
        print()

        # Buscar pagos de la reserva
        pagos = reserva.pagos.all()
        print(f"Pagos registrados: {pagos.count()}")

        giftcard_encontrada = None
        for pago in pagos:
            print(f"\n  Pago ID: {pago.id}")
            print(f"  - Método: {pago.metodo_pago}")
            print(f"  - Monto: ${pago.monto:,.0f}")
            print(f"  - Fecha: {pago.fecha_pago}")

            if pago.metodo_pago == 'giftcard' and pago.giftcard:
                print(f"  - GiftCard asociada: {pago.giftcard.codigo}")
                print(f"    * Monto inicial: ${pago.giftcard.monto_inicial:,.0f}")
                print(f"    * Monto disponible: ${pago.giftcard.monto_disponible:,.0f}")
                print(f"    * Estado: {pago.giftcard.estado}")

                diferencia = pago.giftcard.monto_inicial - pago.monto
                if pago.giftcard.monto_disponible != diferencia:
                    print(f"    * ⚠️ INCONSISTENCIA: Se pagó ${pago.monto:,.0f} pero el saldo es ${pago.giftcard.monto_disponible:,.0f}")
                    print(f"    * ⚠️ Saldo esperado: ${diferencia:,.0f}")
                else:
                    print(f"    * ✓ Saldo correcto")

                giftcard_encontrada = pago.giftcard

        return giftcard_encontrada

    except VentaReserva.DoesNotExist:
        print("❌ ERROR: Reserva 4388 no encontrada")
        return None
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def analizar_todos_pagos_giftcard(giftcard):
    """Analiza todos los pagos realizados con una GiftCard específica"""
    separador(f"ANÁLISIS DE TODOS LOS PAGOS CON GIFTCARD {giftcard.codigo}")

    pagos = Pago.objects.filter(giftcard=giftcard).order_by('fecha_pago')

    print(f"Total de pagos con esta GiftCard: {pagos.count()}\n")

    monto_total_usado = Decimal('0')
    for i, pago in enumerate(pagos, 1):
        print(f"{i}. Pago ID: {pago.id}")
        print(f"   Reserva: #{pago.venta_reserva.id}")
        print(f"   Monto: ${pago.monto:,.0f}")
        print(f"   Fecha: {pago.fecha_pago}")
        monto_total_usado += pago.monto
        print()

    print(f"RESUMEN:")
    print(f"  Monto inicial GiftCard: ${giftcard.monto_inicial:,.0f}")
    print(f"  Total usado en pagos: ${monto_total_usado:,.0f}")
    print(f"  Saldo actual en GiftCard: ${giftcard.monto_disponible:,.0f}")
    print(f"  Saldo esperado: ${giftcard.monto_inicial - monto_total_usado:,.0f}")

    diferencia = giftcard.monto_disponible - (giftcard.monto_inicial - monto_total_usado)
    if diferencia != 0:
        print(f"\n⚠️ INCONSISTENCIA DETECTADA: Diferencia de ${diferencia:,.0f}")
        return True
    else:
        print(f"\n✓ GiftCard consistente")
        return False


def crear_giftcard_prueba_y_simular():
    """Crea una GiftCard de prueba y simula el proceso completo"""
    separador("PRUEBA: CREACIÓN Y USO DE GIFTCARD DE PRUEBA")

    try:
        # Buscar o crear cliente de prueba
        cliente_prueba, created = Cliente.objects.get_or_create(
            telefono='+56900000000',
            defaults={
                'nombre': 'Cliente Prueba GiftCard',
                'email': 'prueba_giftcard@test.com'
            }
        )
        print(f"Cliente de prueba: {cliente_prueba.nombre}")

        # Crear GiftCard de prueba
        giftcard_prueba = GiftCard.objects.create(
            monto_inicial=50000,
            fecha_vencimiento=timezone.now().date() + timedelta(days=365),
            cliente_destinatario=cliente_prueba
        )
        print(f"\n✓ GiftCard creada: {giftcard_prueba.codigo}")
        print(f"  Monto inicial: ${giftcard_prueba.monto_inicial:,.0f}")
        print(f"  Monto disponible: ${giftcard_prueba.monto_disponible:,.0f}")
        print(f"  Estado: {giftcard_prueba.estado}")

        # Crear una reserva de prueba
        reserva_prueba = VentaReserva.objects.create(
            cliente=cliente_prueba,
            total=50000
        )
        print(f"\n✓ Reserva de prueba creada: #{reserva_prueba.id}")

        # Intentar crear un pago con la GiftCard
        print(f"\n→ Intentando crear pago de $30,000 con GiftCard...")
        pago_prueba = Pago(
            venta_reserva=reserva_prueba,
            monto=30000,
            metodo_pago='giftcard',
            giftcard=giftcard_prueba
        )

        # Guardar el pago (esto debería llamar al método save() que ejecuta usar())
        pago_prueba.save()

        print(f"✓ Pago creado exitosamente: ID {pago_prueba.id}")

        # Refrescar la GiftCard desde la BD
        giftcard_prueba.refresh_from_db()

        print(f"\n📊 ESTADO POST-PAGO:")
        print(f"  Monto disponible: ${giftcard_prueba.monto_disponible:,.0f}")
        print(f"  Estado: {giftcard_prueba.estado}")
        print(f"  Saldo esperado: $20,000")

        funciona_correctamente = giftcard_prueba.monto_disponible == 20000

        if funciona_correctamente:
            print(f"\n✓ ¡EL MÉTODO SAVE() FUNCIONA CORRECTAMENTE!")
            print(f"  La GiftCard descontó correctamente el monto usado.")
        else:
            print(f"\n❌ ERROR: El saldo no se actualizó correctamente")
            print(f"  Esperado: $20,000")
            print(f"  Actual: ${giftcard_prueba.monto_disponible:,.0f}")

        # Limpiar: eliminar datos de prueba
        print(f"\n→ Limpiando datos de prueba...")
        pago_prueba.delete()
        reserva_prueba.delete()
        giftcard_prueba.delete()
        if created:
            cliente_prueba.delete()
        print(f"✓ Datos de prueba eliminados")

        return funciona_correctamente

    except Exception as e:
        print(f"\n❌ ERROR en prueba: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def investigar_creacion_manual():
    """Investiga si los pagos fueron creados manualmente saltando el save()"""
    separador("INVESTIGACIÓN: ¿PAGOS CREADOS MANUALMENTE EN ADMIN?")

    print("Analizando formas en que los pagos podrían haberse creado sin ejecutar save():\n")

    print("1. CREACIÓN DIRECTA EN ADMIN:")
    print("   Si un pago se creó en el admin de Django, el método save() SÍ se ejecuta.")
    print("   ✓ Esta NO sería la causa\n")

    print("2. BULK CREATE:")
    print("   Si se usó Pago.objects.bulk_create(), el método save() NO se ejecuta.")
    print("   ⚠️ Esta PODRÍA ser la causa\n")

    print("3. UPDATE DIRECTO:")
    print("   Si se usó Pago.objects.filter(...).update(), el método save() NO se ejecuta.")
    print("   ⚠️ Esta PODRÍA ser la causa\n")

    print("4. IMPORTACIÓN DE DATOS:")
    print("   Si los datos se importaron desde otra fuente sin usar save().")
    print("   ⚠️ Esta PODRÍA ser la causa\n")

    print("5. ADMIN INLINE SIN CONFIGURAR:")
    print("   Si el inline de Pago en VentaReserva no ejecuta save() correctamente.")
    print("   ⚠️ Esta PODRÍA ser la causa\n")


def generar_plan_correccion():
    """Genera un plan de acción para corregir el problema"""
    separador("PLAN DE CORRECCIÓN PROPUESTO")

    print("""
PASOS RECOMENDADOS:

1. AUDITORÍA COMPLETA:
   ✓ Identificar todas las GiftCards con inconsistencias
   ✓ Calcular el saldo correcto basado en pagos registrados
   ✓ Generar reporte de diferencias

2. CORRECCIÓN DE DATOS:
   ✓ Script que recalcule el saldo de todas las GiftCards
   ✓ Verificar cada pago con método 'giftcard'
   ✓ Actualizar monto_disponible y estado correctamente

3. PREVENCIÓN:
   ✓ Asegurar que PagoInline en admin ejecute save()
   ✓ Crear signal post_save para doble verificación
   ✓ Agregar logging de cambios en GiftCard.usar()
   ✓ Test automático para verificar descuento de saldo

4. MONITOREO:
   ✓ Dashboard de GiftCards con inconsistencias
   ✓ Alerta automática si se detecta saldo incorrecto
   ✓ Reporte diario de GiftCards activas
    """)


def main():
    """Función principal que ejecuta todos los diagnósticos"""
    print("\n" + "🔍" * 40)
    print("  DIAGNÓSTICO DE GIFTCARDS - SISTEMA AREMKO")
    print("🔍" * 40)

    # 1. Analizar la GiftCard problemática
    giftcard_problema = analizar_giftcard_problematica()

    if giftcard_problema:
        # 2. Analizar todos los pagos con esa GiftCard
        tiene_inconsistencia = analizar_todos_pagos_giftcard(giftcard_problema)
    else:
        tiene_inconsistencia = False

    # 3. Crear y probar GiftCard de prueba
    prueba_exitosa = crear_giftcard_prueba_y_simular()

    # 4. Investigar posibles causas
    investigar_creacion_manual()

    # 5. Generar plan de corrección
    generar_plan_correccion()

    # CONCLUSIÓN
    separador("CONCLUSIÓN DEL DIAGNÓSTICO")

    if prueba_exitosa and tiene_inconsistencia:
        print("""
✓ EL MÉTODO save() DEL MODELO PAGO FUNCIONA CORRECTAMENTE

Conclusión:
El problema NO es un bug en el código actual. La lógica de descuento
funciona perfectamente cuando se usa el método save() normal.

Causa probable:
Los pagos problemáticos fueron creados de una forma que NO ejecutó
el método save() del modelo (bulk_create, update directo, inline mal
configurado, o importación).

Recomendación INMEDIATA:
1. Ejecutar script de corrección para recalcular saldos de GiftCards
2. Revisar configuración de PagoInline en admin.py
3. Agregar signal de validación post_save
        """)
    elif not prueba_exitosa:
        print("""
❌ EL MÉTODO save() NO FUNCIONÓ EN LA PRUEBA

Conclusión:
Hay un problema en el código actual que impide el descuento correcto.

Siguiente paso:
Revisar el método GiftCard.usar() y Pago.save() para identificar
el problema específico.
        """)
    else:
        print("""
✓ TODO FUNCIONA CORRECTAMENTE

No se detectaron inconsistencias en la GiftCard de la reserva 4388.
Es posible que ya haya sido corregida manualmente.
        """)


if __name__ == "__main__":
    main()
