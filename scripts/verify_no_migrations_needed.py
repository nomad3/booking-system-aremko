#!/usr/bin/env python
"""
Script para verificar que NO necesitamos migraciones nuevas
para la implementación de Luna Reservation API

Ejecutar: python scripts/verify_no_migrations_needed.py
"""

import os
import sys
import django

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

try:
    django.setup()
except Exception:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
    try:
        django.setup()
    except Exception:
        for possible_name in ['aremko_project.settings', 'config.settings', 'mysite.settings']:
            try:
                os.environ['DJANGO_SETTINGS_MODULE'] = possible_name
                django.setup()
                break
            except:
                continue

from django.db import connection
from ventas.models import Cliente, VentaReserva, ReservaServicio, Servicio, Pago, Region, Comuna

print("\n" + "="*60)
print("VERIFICACIÓN: NO SE NECESITAN MIGRACIONES PARA LUNA API")
print("="*60)

print("\n📋 Verificando modelos existentes necesarios para Luna API...")

# Modelos que Luna API usará
modelos_necesarios = {
    'Cliente': Cliente,
    'VentaReserva': VentaReserva,
    'ReservaServicio': ReservaServicio,
    'Servicio': Servicio,
    'Pago': Pago,
    'Region': Region,
    'Comuna': Comuna
}

errores = []

for nombre, modelo in modelos_necesarios.items():
    print(f"\n🔍 Verificando modelo: {nombre}")

    try:
        # Verificar que la tabla existe
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = '{modelo._meta.db_table}'
            """)
            result = cursor.fetchone()

            if result:
                print(f"   ✅ Tabla '{modelo._meta.db_table}' existe")
            else:
                print(f"   ❌ Tabla '{modelo._meta.db_table}' NO existe")
                errores.append(f"Tabla {modelo._meta.db_table} no existe")
                continue

        # Verificar campos críticos según el modelo
        campos_criticos = {
            'Cliente': ['nombre', 'telefono', 'email', 'documento_identidad', 'region_id', 'comuna_id'],
            'VentaReserva': ['cliente_id', 'total', 'pagado', 'estado_pago', 'estado_reserva', 'fecha_creacion'],
            'ReservaServicio': ['venta_reserva_id', 'servicio_id', 'fecha_agendamiento', 'hora_inicio', 'cantidad_personas', 'precio_unitario_venta'],
            'Servicio': ['nombre', 'precio_base', 'capacidad_minima', 'capacidad_maxima', 'activo', 'publicado_web', 'slots_disponibles'],
            'Pago': ['venta_reserva_id', 'monto', 'metodo_pago', 'fecha_pago'],
            'Region': ['nombre'],
            'Comuna': ['nombre', 'region_id']
        }

        if nombre in campos_criticos:
            campos_faltantes = []

            for campo in campos_criticos[nombre]:
                # Remover _id para ForeignKeys para verificar en el modelo
                campo_real = campo.replace('_id', '')

                # Verificar usando _meta.get_field que es más confiable
                try:
                    modelo._meta.get_field(campo_real)
                    print(f"   ✅ Campo '{campo}' existe")
                except Exception:
                    # Fallback a hasattr para campos no estándar
                    if hasattr(modelo, campo_real):
                        print(f"   ✅ Campo '{campo}' existe")
                    else:
                        campos_faltantes.append(campo)
                        print(f"   ⚠️  Campo '{campo}' no encontrado")

            if campos_faltantes:
                errores.append(f"{nombre}: campos faltantes {campos_faltantes}")

        # Verificar que podemos crear una instancia de prueba (sin guardar)
        if nombre == 'Cliente':
            try:
                test_instance = modelo(
                    nombre="Test",
                    telefono="+56912345678",
                    email="test@test.com"
                )
                print(f"   ✅ Modelo {nombre} se puede instanciar")
            except Exception as e:
                print(f"   ⚠️  Error al instanciar {nombre}: {e}")

    except Exception as e:
        print(f"   ❌ Error verificando {nombre}: {e}")
        errores.append(f"{nombre}: {str(e)}")

# Verificar métodos críticos
print("\n🔧 Verificando métodos críticos...")

metodos_criticos = [
    (VentaReserva, 'calcular_total', 'Calcular total de reserva'),
    (VentaReserva, 'actualizar_saldo', 'Actualizar saldo de reserva'),
    (ReservaServicio, 'calcular_precio', 'Calcular precio de servicio'),
    (Cliente, 'numero_visitas', 'Contar visitas del cliente'),
]

for modelo, metodo, descripcion in metodos_criticos:
    if hasattr(modelo, metodo):
        print(f"   ✅ {modelo.__name__}.{metodo}() - {descripcion}")
    else:
        print(f"   ⚠️  {modelo.__name__}.{metodo}() NO encontrado - {descripcion}")
        errores.append(f"Método {modelo.__name__}.{metodo}() faltante")

# Verificar servicios existentes
print("\n📦 Verificando servicios disponibles...")

from ventas.services import cliente_service, pack_descuento_service

servicios_necesarios = [
    ('cliente_service', 'ClienteService', 'Gestión de clientes'),
    ('pack_descuento_service', 'PackDescuentoService', 'Descuentos por packs'),
]

for servicio_module, servicio_class, descripcion in servicios_necesarios:
    try:
        if servicio_module == 'cliente_service':
            from ventas.services.cliente_service import ClienteService
            print(f"   ✅ ClienteService disponible - {descripcion}")
        elif servicio_module == 'pack_descuento_service':
            from ventas.services.pack_descuento_service import PackDescuentoService
            print(f"   ✅ PackDescuentoService disponible - {descripcion}")
    except ImportError as e:
        print(f"   ⚠️  {servicio_class} NO disponible - {descripcion}")
        errores.append(f"Servicio {servicio_class} faltante")

# Verificar funciones de utilidad
print("\n🛠️  Verificando funciones de utilidad...")

try:
    from ventas.calendar_utils import verificar_disponibilidad
    print("   ✅ verificar_disponibilidad() disponible")
except ImportError:
    print("   ⚠️  verificar_disponibilidad() NO disponible")
    errores.append("Función verificar_disponibilidad faltante")

try:
    from ventas.models import ServicioBloqueo, ServicioSlotBloqueo
    print("   ✅ ServicioBloqueo y ServicioSlotBloqueo disponibles")

    # Verificar métodos estáticos
    if hasattr(ServicioBloqueo, 'servicio_bloqueado_en_fecha'):
        print("   ✅ ServicioBloqueo.servicio_bloqueado_en_fecha() existe")
    else:
        print("   ⚠️  ServicioBloqueo.servicio_bloqueado_en_fecha() NO existe")
        errores.append("Método ServicioBloqueo.servicio_bloqueado_en_fecha() faltante")

    if hasattr(ServicioSlotBloqueo, 'slot_bloqueado'):
        print("   ✅ ServicioSlotBloqueo.slot_bloqueado() existe")
    else:
        print("   ⚠️  ServicioSlotBloqueo.slot_bloqueado() NO existe")
        errores.append("Método ServicioSlotBloqueo.slot_bloqueado() faltante")

except ImportError as e:
    print(f"   ⚠️  Error importando bloqueos: {e}")
    errores.append("Modelos de bloqueo no disponibles")

# Resultado final
print("\n" + "="*60)
print("RESULTADO DE LA VERIFICACIÓN")
print("="*60)

if errores:
    print("\n❌ SE ENCONTRARON PROBLEMAS:")
    for error in errores:
        print(f"   - {error}")
    print("\n⚠️  ATENCIÓN: Puede que necesitemos migraciones o correcciones")
    sys.exit(1)
else:
    print("\n✅ VERIFICACIÓN EXITOSA!")
    print("\n✨ Todos los modelos, campos y métodos necesarios están disponibles")
    print("✨ NO se requieren migraciones para implementar Luna Reservation API")
    print("✨ La implementación solo agregará nuevos archivos de views y URLs")
    print("\n📝 Próximos pasos:")
    print("   1. Hacer backup de base de datos en Render")
    print("   2. Crear tag de git: git tag pre-luna-api-v1.0")
    print("   3. Comenzar implementación de Fase 1")
    sys.exit(0)

print("\n" + "="*60)