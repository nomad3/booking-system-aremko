"""
Script de diagnóstico para el problema del Premio #54
Investiga por qué se generó premio de bienvenida para clienta con historial
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto.settings')
django.setup()

from ventas.models import ClientePremio, Cliente, ReservaServicio
from ventas.services.tramo_service import TramoService
from ventas.services.crm_service import CRMService

print("\n" + "=" * 80)
print("🔍 DIAGNÓSTICO DEL PREMIO #54")
print("=" * 80 + "\n")

# Obtener el premio #54
try:
    premio = ClientePremio.objects.select_related('cliente', 'premio').get(id=54)
except ClientePremio.DoesNotExist:
    print("❌ Premio #54 no existe")
    sys.exit(1)

print(f"📋 INFORMACIÓN DEL PREMIO")
print(f"   ID: {premio.id}")
print(f"   Cliente: {premio.cliente.nombre}")
print(f"   Tipo: {premio.premio.tipo}")
print(f"   Nombre: {premio.premio.nombre}")
print(f"   Estado: {premio.estado}")
print(f"   Fecha ganado: {premio.fecha_ganado}")
print(f"   Gasto al ganar: ${premio.gasto_total_al_ganar:,.0f}")
print(f"   Tramo al ganar: {premio.tramo_al_ganar}")
print()

# Analizar el cliente
cliente = premio.cliente

print(f"👤 ANÁLISIS DEL CLIENTE: {cliente.nombre}")
print(f"   ID: {cliente.id}")
print(f"   Teléfono: {cliente.telefono}")
print()

# Obtener datos 360 del cliente (incluye históricos)
try:
    datos_360 = CRMService.get_customer_360(cliente.id)
    print(f"📊 DATOS 360 (Sistema Actual + Históricos):")
    print(f"   Total servicios: {datos_360['metricas']['total_servicios']}")
    print(f"   Servicios actuales: {datos_360['metricas']['servicios_actuales']}")
    print(f"   Servicios históricos: {datos_360['metricas']['servicios_historicos']}")
    print(f"   Gasto total: ${datos_360['metricas']['gasto_total']:,.0f}")
    print(f"   Gasto histórico: ${datos_360['metricas']['gasto_historico']:,.0f}")
    print(f"   Gasto actual: ${datos_360['metricas']['gasto_actual']:,.0f}")
    print()
except Exception as e:
    print(f"❌ Error obteniendo datos 360: {e}")
    print()

# Verificar método es_cliente_nuevo
es_nuevo = TramoService.es_cliente_nuevo(cliente)
print(f"❓ TramoService.es_cliente_nuevo() retorna: {es_nuevo}")
print()

# Obtener primera reserva de servicio en el sistema actual
primera_reserva = ReservaServicio.objects.filter(
    venta_reserva__cliente=cliente
).order_by('fecha_agendamiento', 'id').first()

if primera_reserva:
    print(f"📅 PRIMERA RESERVA EN SISTEMA ACTUAL:")
    print(f"   Fecha: {primera_reserva.fecha_agendamiento}")
    print(f"   Servicio: {primera_reserva.servicio.nombre if primera_reserva.servicio else 'N/A'}")
    print(f"   Hora: {primera_reserva.hora_inicio}")
    print(f"   Reserva ID: {primera_reserva.venta_reserva_id}")
else:
    print(f"❌ No se encontró primera reserva en sistema actual")
print()

# Análisis del problema
print("=" * 80)
print("🔍 ANÁLISIS DEL PROBLEMA")
print("=" * 80 + "\n")

print("PROBLEMA IDENTIFICADO:")
print()
print("1. La clienta tiene 9 servicios en total:")
print("   • 1 servicio en sistema actual (VentaReserva)")
print("   • 8 servicios en tabla de servicios históricos")
print()
print("2. Gasto total real: $409,000 (debería estar en Tramo 9)")
print()
print("3. Sistema generó premio de 'Descuento de Bienvenida' (Primera Compra)")
print("   cuando debería haber generado premio por Tramo 9")
print()

# Verificar la lógica del comando procesar_premios_bienvenida
print("CAUSA RAÍZ:")
print()
print("El comando 'procesar_premios_bienvenida.py' (líneas 93-103) solo verifica:")
print()
print("   primera_reserva = ReservaServicio.objects.filter(")
print("       venta_reserva__cliente=cliente")
print("   ).order_by('fecha_agendamiento', 'id').first()")
print()
print("   if not primera_reserva or primera_reserva.fecha_agendamiento != fecha_objetivo:")
print("       continue  # No es su primera reserva")
print()
print("❌ PROBLEMA: Solo busca en ReservaServicio del sistema ACTUAL.")
print("❌ NO considera la tabla de servicios históricos.")
print()
print("La lógica correcta debería usar:")
print("   • TramoService.es_cliente_nuevo(cliente)")
print("   • O verificar CRMService.get_customer_360()['metricas']['total_servicios']")
print()

print("=" * 80)
print("✅ SOLUCIÓN REQUERIDA")
print("=" * 80 + "\n")

print("1. Modificar el comando 'procesar_premios_bienvenida.py'")
print("   para usar TramoService.es_cliente_nuevo() en vez de buscar")
print("   solo en ReservaServicio")
print()
print("2. Modificar signal 'actualizar_tramo_y_premios_on_pago' en ventas/signals.py")
print("   para verificar correctamente si es cliente nuevo considerando históricos")
print()
print("3. Anular el Premio #54 y generar el premio correcto por Tramo 9")
print()

# Calcular qué premio debería tener
gasto_total = TramoService.calcular_gasto_cliente(cliente)
tramo_actual = TramoService.calcular_tramo(float(gasto_total))

print(f"PREMIO CORRECTO PARA ESTA CLIENTA:")
print(f"   Gasto total: ${gasto_total:,.0f}")
print(f"   Tramo actual: {tramo_actual}")
print(f"   Debería recibir: Premio por Tramo {tramo_actual}")
print()

print("=" * 80)
