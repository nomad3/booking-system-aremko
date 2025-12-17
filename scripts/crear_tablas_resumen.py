#!/usr/bin/env python3
"""
Script para crear manualmente las tablas de ConfiguracionResumen
Ejecutar: python scripts/crear_tablas_resumen.py
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')

import django
django.setup()

from django.db import connection

print("\n" + "=" * 80)
print("CREAR TABLAS PARA SISTEMA DE RESUMEN DE RESERVA")
print("=" * 80)

with connection.cursor() as cursor:
    print("\n1. Creando tabla ventas_configuracionresumen...")
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ventas_configuracionresumen (
                id BIGSERIAL PRIMARY KEY,
                encabezado TEXT NOT NULL DEFAULT 'Confirma tu Reserva en Aremko Spa',
                datos_transferencia TEXT NOT NULL DEFAULT 'Para confirmación reserva abonar 100% a:

Aremko Hotel Spa Rut 76.485.192-7
Mercado Pago Cta Vista 1016006859

Para confirmar su reserva nos debe llegar un correo de la entidad pagadora al realizar la transferencia ingrese el correo ventas@aremko.cl, indicando NRO Reserva y fecha de esta reserva.

La reserva se considerará confirmada únicamente una vez recibido el comprobante en el correo y también despachar imagen por este medio donde se especifica claramente detalles de la transferencia.',
                link_pago_mercadopago VARCHAR(200) NOT NULL DEFAULT 'https://link.mercadopago.cl/aremko',
                texto_link_pago TEXT NOT NULL DEFAULT 'Ingresa al link, elige cómo pagar, ¡y listo!',
                tina_yate_texto TEXT NOT NULL DEFAULT 'Tina Yate agua fría (sin costo adicional)
Temperatura garantizada menos de 37°grados su tina es gratis
No incluye toallas o batas.',
                sauna_no_disponible TEXT NOT NULL DEFAULT '(Reserva no incluye sauna por que este no está disponible)',
                politica_alojamiento TEXT NOT NULL DEFAULT 'Alojamiento : Si nos avisa con más de 48hrs de anticipación antes de que inicie su reserva (16:00 hrs Check in), se puede pedir reembolso total o cambio de fecha sin penalidad. Si no se avisa con menos de 48hrs antes de su reserva, lamentablemente la has perdido.',
                politica_tinas_masajes TEXT NOT NULL DEFAULT 'Tina / Masajes : Si nos avisa con más de 24hrs de anticipación antes de que inicie su reserva, se puede pedir reembolso total o cambio de fecha sin penalidad. Si no se avisa con menos de 24hrs antes de su reserva, lamentablemente la has perdido.',
                equipamiento_cabanas TEXT NOT NULL DEFAULT 'Cabaña equipada:*
Nuestras cabañas cuentan con todas las comodidades para que disfrutes al máximo: mini refrigerador, microondas, lavaplatos, tostadora, hervidor, loza, aire acondicionado, wifi y secador de pelo.',
                cortesias_alojamiento TEXT NOT NULL DEFAULT 'Detalle especial:
Te ofrecemos cortesías como té negro, infusiones especiales y té Twinings para endulzar naturalmente tus momentos de relax.',
                seguridad_pasarela TEXT NOT NULL DEFAULT 'Pasarela:
Por tu seguridad, al transitar por las pasarelas, te pedimos usar zapatos cómodos y antideslizantes. El uso de pasamanos es obligatorio y las sandalias no están permitidas.',
                cortesias_generales TEXT NOT NULL DEFAULT 'Cortesías: Durante tu estadía encontrarás en recepción un espacio de autoservicio de té e infusiones.',
                despedida TEXT NOT NULL DEFAULT 'Estamos aquí para asegurarnos de que tengas una experiencia inolvidable. Si tienes dudas o necesitas algo más, no dudes en escribirnos.

Gracias por elegir Aremko Spa para tu relax.'
            );
        """)
        print("   ✅ Tabla ventas_configuracionresumen creada exitosamente")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
        print("   (Probablemente la tabla ya existe)")

    print("\n2. Agregando campo informacion_adicional a ventas_servicio...")
    try:
        cursor.execute("""
            ALTER TABLE ventas_servicio
            ADD COLUMN IF NOT EXISTS informacion_adicional TEXT NOT NULL DEFAULT '';
        """)
        print("   ✅ Campo informacion_adicional agregado exitosamente")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
        print("   (Probablemente el campo ya existe)")

    print("\n3. Insertando registro inicial en ConfiguracionResumen...")
    try:
        cursor.execute("""
            INSERT INTO ventas_configuracionresumen (id)
            SELECT 1
            WHERE NOT EXISTS (SELECT 1 FROM ventas_configuracionresumen WHERE id = 1);
        """)
        print("   ✅ Registro inicial creado")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")

print("\n" + "=" * 80)
print("COMPLETADO")
print("=" * 80)
print("\n✨ Las tablas han sido creadas exitosamente")
print("   Ahora puedes usar el sistema de Resumen de Reserva\n")
