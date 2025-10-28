"""
Script de prueba para verificar el SQL fix de multiplicación cartesiana
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

# Probar con Enzo Magnani (ID: 203)
ENZO_ID = 203

print("\n" + "="*80)
print("🧪 TEST: SQL Fix para Multiplicación Cartesiana")
print("="*80 + "\n")

print("Probando con Enzo Magnani (ID: 203)")
print("Valores esperados:")
print("  - Servicios actuales: 5")
print("  - Gasto actual: $205,000")
print("  - Servicios históricos: 2")
print("  - Gasto histórico: $70,000")
print("  - Total: $275,000")
print()

query = """
SELECT
    c.id as cliente_id,
    c.nombre,
    c.email,
    -- Subconsulta para servicios actuales
    (SELECT COUNT(DISTINCT rs2.id)
     FROM ventas_ventareserva vr2
     JOIN ventas_reservaservicio rs2 ON vr2.id = rs2.venta_reserva_id
     WHERE vr2.cliente_id = c.id AND vr2.estado_pago IN ('pagado', 'parcial')
    ) as servicios_actuales,
    (SELECT COALESCE(SUM(CAST(s2.precio_base AS DECIMAL) * COALESCE(rs2.cantidad_personas, 1)), 0)
     FROM ventas_ventareserva vr2
     JOIN ventas_reservaservicio rs2 ON vr2.id = rs2.venta_reserva_id
     JOIN ventas_servicio s2 ON rs2.servicio_id = s2.id
     WHERE vr2.cliente_id = c.id AND vr2.estado_pago IN ('pagado', 'parcial')
    ) as gasto_actual,
    -- Subconsulta para servicios históricos
    (SELECT COUNT(DISTINCT sh2.id)
     FROM crm_service_history sh2
     WHERE sh2.cliente_id = c.id
    ) as servicios_historicos,
    (SELECT COALESCE(SUM(sh2.price_paid), 0)
     FROM crm_service_history sh2
     WHERE sh2.cliente_id = c.id
    ) as gasto_historico,
    -- Totales combinados
    ((SELECT COUNT(DISTINCT rs2.id)
      FROM ventas_ventareserva vr2
      JOIN ventas_reservaservicio rs2 ON vr2.id = rs2.venta_reserva_id
      WHERE vr2.cliente_id = c.id AND vr2.estado_pago IN ('pagado', 'parcial')
     ) +
     (SELECT COUNT(DISTINCT sh2.id)
      FROM crm_service_history sh2
      WHERE sh2.cliente_id = c.id
     )) as total_servicios,
    ((SELECT COALESCE(SUM(CAST(s2.precio_base AS DECIMAL) * COALESCE(rs2.cantidad_personas, 1)), 0)
      FROM ventas_ventareserva vr2
      JOIN ventas_reservaservicio rs2 ON vr2.id = rs2.venta_reserva_id
      JOIN ventas_servicio s2 ON rs2.servicio_id = s2.id
      WHERE vr2.cliente_id = c.id AND vr2.estado_pago IN ('pagado', 'parcial')
     ) +
     (SELECT COALESCE(SUM(sh2.price_paid), 0)
      FROM crm_service_history sh2
      WHERE sh2.cliente_id = c.id
     )) as total_gasto
FROM ventas_cliente c
WHERE c.id = %s
"""

try:
    with connection.cursor() as cursor:
        cursor.execute(query, [ENZO_ID])
        row = cursor.fetchone()
        columns = [col[0] for col in cursor.description]
        result = dict(zip(columns, row))

        print("-" * 80)
        print("📊 RESULTADOS DEL SQL:")
        print("-" * 80)
        print(f"Cliente ID: {result['cliente_id']}")
        print(f"Nombre: {result['nombre']}")
        print(f"Email: {result['email']}")
        print()
        print(f"Servicios actuales: {result['servicios_actuales']}")
        print(f"Gasto actual: ${float(result['gasto_actual']):,.0f}")
        print()
        print(f"Servicios históricos: {result['servicios_historicos']}")
        print(f"Gasto histórico: ${float(result['gasto_historico']):,.0f}")
        print()
        print(f"Total servicios: {result['total_servicios']}")
        print(f"Total gasto: ${float(result['total_gasto']):,.0f}")
        print("-" * 80)
        print()

        # Verificar resultados
        expected = {
            'servicios_actuales': 5,
            'gasto_actual': 205000,
            'servicios_historicos': 2,
            'gasto_historico': 70000,
            'total_servicios': 7,
            'total_gasto': 275000
        }

        print("="*80)
        print("✅ VERIFICACIÓN:")
        print("="*80)

        all_correct = True
        for key, expected_value in expected.items():
            actual_value = result[key]
            if key.startswith('gasto'):
                actual_value = float(actual_value)

            status = "✅" if actual_value == expected_value else "❌"
            print(f"{status} {key}: {actual_value} (esperado: {expected_value})")

            if actual_value != expected_value:
                all_correct = False

        print("="*80)
        print()

        if all_correct:
            print("🎉 ¡TODOS LOS VALORES SON CORRECTOS!")
            print("✅ El SQL fix funciona perfectamente")
            print("✅ No hay multiplicación cartesiana")
        else:
            print("❌ HAY DIFERENCIAS - Revisar el SQL")

except Exception as e:
    print(f"❌ Error ejecutando query: {e}")
    import traceback
    traceback.print_exc()
