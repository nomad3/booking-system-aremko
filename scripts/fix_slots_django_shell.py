# Script de CORRECCIÓN para ejecutar en Django Shell
# Ejecuta: python manage.py shell
# Luego copia y pega este código

from ventas.models import Servicio
from django.db import transaction
from datetime import datetime, timedelta

print("\n" + "="*60)
print("CORRECCIÓN DE IDIOMA EN SLOTS_DISPONIBLES")
print("="*60)

# Mapeo de días español -> inglés
dias_map = {
    'lunes': 'monday',
    'martes': 'tuesday',
    'miércoles': 'wednesday',
    'miercoles': 'wednesday',  # Sin tilde
    'jueves': 'thursday',
    'viernes': 'friday',
    'sábado': 'saturday',
    'sabado': 'saturday',  # Sin tilde
    'domingo': 'sunday'
}

# Buscar todos los servicios con slots_disponibles configurados
servicios = Servicio.objects.filter(
    activo=True,
    slots_disponibles__isnull=False
)

print(f"\n📋 Servicios a revisar: {servicios.count()}")

servicios_actualizados = 0
servicios_con_problemas = []

with transaction.atomic():
    for servicio in servicios:
        print(f"\n🔍 Revisando: {servicio.nombre} (ID: {servicio.id})")

        if not isinstance(servicio.slots_disponibles, dict):
            print(f"   ⚠️  No es un diccionario, es {type(servicio.slots_disponibles)}")
            servicios_con_problemas.append(servicio)
            continue

        slots_original = servicio.slots_disponibles.copy()
        slots_nuevo = {}
        necesita_actualizacion = False

        for dia, horarios in slots_original.items():
            dia_lower = dia.lower()

            # Si el día está en español, convertir a inglés
            if dia_lower in dias_map:
                dia_ingles = dias_map[dia_lower]
                slots_nuevo[dia_ingles] = horarios
                necesita_actualizacion = True
                print(f"   ✅ Convirtiendo '{dia}' -> '{dia_ingles}': {len(horarios) if horarios else 0} slots")
            # Si ya está en inglés, mantener
            elif dia_lower in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
                slots_nuevo[dia_lower] = horarios
                print(f"   ✓ Ya en inglés '{dia}': {len(horarios) if horarios else 0} slots")
            else:
                # Día no reconocido
                print(f"   ❌ Día no reconocido: '{dia}'")
                slots_nuevo[dia] = horarios

        if necesita_actualizacion:
            servicio.slots_disponibles = slots_nuevo
            servicio.save(update_fields=['slots_disponibles'])
            servicios_actualizados += 1
            print(f"   💾 ACTUALIZADO")
        else:
            print(f"   ↔️  Sin cambios necesarios")

print("\n" + "="*60)
print("RESUMEN DE LA CORRECCIÓN")
print("="*60)
print(f"✅ Servicios actualizados: {servicios_actualizados}")
print(f"⚠️  Servicios con problemas: {len(servicios_con_problemas)}")

if servicios_con_problemas:
    print("\nServicios que necesitan revisión manual:")
    for s in servicios_con_problemas:
        print(f"  - {s.nombre} (ID: {s.id})")

# Verificar específicamente Tina Calbuco
print("\n" + "="*60)
print("VERIFICACIÓN ESPECÍFICA: TINA CALBUCO")
print("="*60)

from django.db.models import Q
calbuco = Servicio.objects.filter(
    Q(nombre__icontains='calbuco') | Q(id=4)
).first()

if calbuco:
    print(f"\n✅ Tina Calbuco encontrada: {calbuco.nombre} (ID: {calbuco.id})")
    if isinstance(calbuco.slots_disponibles, dict):
        print("   Configuración actual:")
        for dia, slots in calbuco.slots_disponibles.items():
            print(f"      {dia}: {len(slots) if slots else 0} slots")

        # Probar disponibilidad para mañana
        tomorrow = datetime.now().date() + timedelta(days=1)
        day_name = tomorrow.strftime('%A').lower()
        slots_manana = calbuco.slots_disponibles.get(day_name, [])

        print(f"\n   Prueba para mañana ({tomorrow}, {day_name}):")
        print(f"   Slots disponibles: {len(slots_manana)}")
        if slots_manana:
            print(f"   Horarios: {slots_manana[:5]}...")  # Primeros 5
else:
    print("❌ No se encontró Tina Calbuco")

print("\n✅ Corrección completada")
print("\nPrueba la API con:")
print(f"curl -X GET 'https://aremko.cl/ventas/get-available-hours/?servicio_id=4&fecha={datetime.now().date() + timedelta(days=1)}'")