# Script para ejecutar en Django Shell
# Ejecuta: python manage.py shell
# Luego copia y pega este código

from datetime import datetime, timedelta
from ventas.models import Servicio, CategoriaServicio, ReservaServicio, ServicioBloqueo, ServicioSlotBloqueo
from django.db.models import Q, Count

print("\n" + "="*60)
print("DIAGNÓSTICO: TINA CALBUCO - PROBLEMA DE DISPONIBILIDAD")
print("="*60)

# Fecha de mañana
tomorrow = datetime.now().date() + timedelta(days=1)
day_name_english = tomorrow.strftime('%A').lower()  # English day name

# También calcular el nombre del día en español
dias_espanol = {
    'monday': 'lunes',
    'tuesday': 'martes',
    'wednesday': 'miércoles',
    'thursday': 'jueves',
    'friday': 'viernes',
    'saturday': 'sábado',
    'sunday': 'domingo'
}
day_name_spanish = dias_espanol.get(day_name_english, day_name_english)

print(f"\n📅 Fecha de mañana: {tomorrow}")
print(f"   Día en inglés: {day_name_english}")
print(f"   Día en español: {day_name_spanish}")

# Buscar Tina Calbuco
calbuco = Servicio.objects.filter(
    Q(nombre__icontains='calbuco') | Q(id=4)
).first()

if not calbuco:
    print("\n❌ No se encontró Tina Calbuco")
    print("\nBuscando todas las tinajas...")
    tinajas = Servicio.objects.filter(
        Q(nombre__icontains='tina') |
        Q(nombre__icontains='tinaja')
    )
    for tina in tinajas:
        print(f"  ID {tina.id}: {tina.nombre}")
else:
    print(f"\n✅ Encontrada: {calbuco.nombre} (ID: {calbuco.id})")
    print(f"   Activo: {calbuco.activo}")
    print(f"   Publicado web: {calbuco.publicado_web}")
    print(f"   Precio: ${calbuco.precio_base:,.0f}")

    # Verificar capacidad
    max_simultaneos = getattr(calbuco, 'max_servicios_simultaneos', 1)
    print(f"   Max servicios simultáneos: {max_simultaneos}")

    # CRÍTICO: Verificar estructura de slots_disponibles
    print(f"\n🔍 ANÁLISIS DE SLOTS_DISPONIBLES:")
    print(f"   Tipo: {type(calbuco.slots_disponibles)}")

    if calbuco.slots_disponibles is None:
        print("   ⚠️  slots_disponibles es NULL")
    elif isinstance(calbuco.slots_disponibles, dict):
        print(f"   ✅ Es un diccionario con claves: {list(calbuco.slots_disponibles.keys())}")

        # Verificar si tiene el día en inglés
        if day_name_english in calbuco.slots_disponibles:
            slots_english = calbuco.slots_disponibles[day_name_english]
            print(f"   ✅ Tiene slots para '{day_name_english}': {slots_english}")
        else:
            print(f"   ❌ NO tiene slots para '{day_name_english}'")

        # Verificar si tiene el día en español
        if day_name_spanish in calbuco.slots_disponibles:
            slots_spanish = calbuco.slots_disponibles[day_name_spanish]
            print(f"   ⚠️  Tiene slots para '{day_name_spanish}': {slots_spanish}")
            print("      PROBLEMA: Los slots están en español pero el código busca en inglés!")

        # Mostrar todas las claves y sus valores
        print("\n   Configuración actual completa:")
        for key, value in calbuco.slots_disponibles.items():
            print(f"      '{key}': {value[:3] if value else []}...")  # Solo primeros 3 slots

    # Verificar bloqueos
    print(f"\n🚫 VERIFICACIÓN DE BLOQUEOS:")

    # Bloqueo por día completo
    if ServicioBloqueo.servicio_bloqueado_en_fecha(calbuco.id, tomorrow):
        print(f"   ❌ El servicio está BLOQUEADO para {tomorrow}")
    else:
        print(f"   ✅ No hay bloqueo de día completo para {tomorrow}")

    # Verificar reservas existentes
    print(f"\n📋 RESERVAS EXISTENTES PARA {tomorrow}:")
    reservas = ReservaServicio.objects.filter(
        servicio=calbuco,
        fecha_agendamiento=tomorrow
    ).exclude(
        venta_reserva__estado_reserva='cancelada'
    )

    if reservas.exists():
        reservas_por_hora = reservas.values('hora_inicio').annotate(cantidad=Count('id'))
        for r in reservas_por_hora:
            print(f"   {r['hora_inicio']}: {r['cantidad']} reserva(s)")
    else:
        print("   ✅ No hay reservas para mañana")

    # DIAGNÓSTICO
    print("\n" + "="*60)
    print("💡 DIAGNÓSTICO:")
    print("="*60)

    if isinstance(calbuco.slots_disponibles, dict):
        if day_name_spanish in calbuco.slots_disponibles and day_name_english not in calbuco.slots_disponibles:
            print("""
❌ PROBLEMA IDENTIFICADO:
   Los slots están configurados con días en ESPAÑOL
   pero el código busca días en INGLÉS

✅ SOLUCIÓN:
   Ejecuta el script de corrección (ver siguiente archivo)
            """)
        elif not calbuco.slots_disponibles:
            print("""
❌ PROBLEMA: No hay slots configurados
            """)
    else:
        print("""
❌ PROBLEMA: slots_disponibles no es un diccionario
        """)