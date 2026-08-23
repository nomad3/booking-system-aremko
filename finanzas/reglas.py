# -*- coding: utf-8 -*-
"""El plan de cuentas de Aremko y las reglas de clasificación automática.

Definido POR JORGE el 2026-08-08 a partir de sus gastos reales — no de un
manual. Decisiones clave suyas:
- Nancy Mansilla, Claudio Silva y Rafael Pérez son SUELDOS (personal).
- Masajistas (honorarios contra boleta): Carolina Vidal, Sandra Pantoja,
  Paul Salinas, Sofía Plaza.
- Cintia Brinzo y Javiera Pérez son gasto PERSONAL de Alda.
- Los pagos a Cristian Aguilera son INFRAESTRUCTURA (Render y otras cuentas),
  no personales.
- La transferencia a Jorge incluye el presupuesto de Martín ($300.000/mes que
  Jorge le pasa a diario desde su CuentaRUT) — ese monto se reasigna A MANO
  cada mes a Personales Martín.
- Los retiros de Alda quedan «por analizar» hasta revisarlos con ella.
- Combustibles y comercios REDCOMPRA ambiguos se asignan a mano en el admin.
"""

# clave → (nombre, clase, grupo). El comando aplicar_plan_cuentas sincroniza
# esto contra la BD (crea lo que falte, actualiza nombre/grupo de lo existente).
PLAN_CUENTAS = {
    # Personal y honorarios
    'remuneraciones': ('Remuneraciones', 'gasto', 'personal'),
    'imposiciones': ('Imposiciones (vía Patricio Rubio → Previred)', 'gasto', 'personal'),
    'honorarios_masajistas': ('Honorarios masajistas', 'gasto', 'masajistas'),
    # Servicios
    'energia_electrica': ('Energía eléctrica (Crell)', 'gasto', 'energia'),
    'publicidad': ('Publicidad', 'gasto', 'marketing'),
    'infraestructura': ('Infraestructura web e IA', 'gasto', 'infra_web'),
    'comisiones': ('Comisiones de pasarelas y banco', 'gasto', 'admin_fin'),
    'contabilidad': ('Contabilidad (honorarios contador)', 'gasto', 'admin_fin'),
    'seguros': ('Seguros', 'gasto', 'admin_fin'),
    'servicios_basicos': ('Servicios básicos y telefonía', 'gasto', 'admin_fin'),
    # Operación
    'insumos': ('Alimentos e insumos', 'gasto', 'operacion'),
    'mantencion': ('Mantención y reparaciones', 'gasto', 'operacion'),
    'transporte_fletes': ('Transporte y fletes de insumos', 'gasto', 'operacion'),
    'combustible': ('Combustible generador y vehículos', 'gasto', 'combustibles'),
    # Impuestos
    'impuestos': ('Impuestos (SII, patente municipal)', 'gasto', 'impuestos'),
    # Devoluciones: NO son gasto — son ingreso que se revierte (el Pago
    # original queda registrado, decisión de Jorge 2026-08-08). El Resumen las
    # resta de los INGRESOS; en el flujo de caja salen normal (plata real).
    # Se asignan A MANO en el admin (una TEF a cliente no se distingue sola).
    'devoluciones': ('Devoluciones a clientes', 'gasto', 'devoluciones'),
    # Personales / retiros de la familia
    'personales_martin': ('Retiros Martín (presupuesto $300.000/mes)', 'gasto', 'personales_martin'),
    'personales_alda': ('Retiros Alda (por analizar con ella)', 'gasto', 'personales_alda'),
    'personales_jorge': ('Retiros Jorge', 'gasto', 'personales_jorge'),
    # Cajón de espera
    'por_clasificar': ('Por clasificar', 'gasto', 'otros'),
    # Línea "TRASPASO DEUDA INTERNAC" de las tarjetas Scotiabank: el gasto en
    # dólares del ciclo, agregado por el banco. Gasto real, NO traspaso; se
    # desglosa a mano cuando se sabe qué compras trae (22/08/2026).
    'tarjeta_internacional': ('Compras internacionales tarjeta (por desglosar)',
                              'gasto', 'otros'),
    # Ingresos
    'otros_ingresos': ('Otros ingresos', 'ingreso', 'ingresos'),
    'liquidacion_flow': ('Liquidación Flow', 'ingreso', 'ingresos'),
    'liquidacion_sumup': ('Liquidación SumUp', 'ingreso', 'ingresos'),
    'transferencias_recibidas': ('Transferencias recibidas', 'ingreso', 'ingresos'),
}

# Los grupos que son retiro de la familia, NO gasto del negocio: el tablero
# los resta aparte para mostrar el resultado operacional.
GRUPOS_FAMILIA = ('personales_martin', 'personales_alda', 'personales_jorge')

# Grupo contra-ingreso: se resta de los ingresos del Resumen, no de los gastos.
GRUPO_DEVOLUCIONES = 'devoluciones'

# (patrón en MAYÚSCULAS contenido en la descripción) → categoría.
# Se evalúan en orden: la primera que calza gana — lo específico va primero.
REGLAS = [
    # Personal (sueldos)
    ('DEBORAH GONZALEZ', 'remuneraciones'),
    ('NANCY MANSILLA', 'remuneraciones'),
    ('CLAUDIO SILVA', 'remuneraciones'),
    ('RAFAEL PEREZ', 'remuneraciones'),
    ('PATRICIO RUBIO', 'imposiciones'),
    # Masajistas
    ('VIDAL PANTOJA CAROLINA', 'honorarios_masajistas'),
    ('CAROLINA VIDAL', 'honorarios_masajistas'),
    ('PANTOJA CIFUENTES SANDRA', 'honorarios_masajistas'),
    ('SANDRA PANTOJA', 'honorarios_masajistas'),
    ('PAUL SALINAS', 'honorarios_masajistas'),
    ('SOFIA PLAZA', 'honorarios_masajistas'),
    # Personales Alda (incluye a Cintia y Javiera, decisión de Jorge)
    ('ANGELICA TOLOZA', 'personales_alda'),
    ('TOLOZA POBLETE ALDA', 'personales_alda'),
    ('ALDA BCI', 'personales_alda'),
    ('ALDA TOLOZA', 'personales_alda'),
    ('CINTIA BRINZO', 'personales_alda'),
    ('JAVIERA PEREZ', 'personales_alda'),
    # Personales Martín y Jorge
    ('MARTIN AGUILERA', 'personales_martin'),
    ('JORGE AGUILERA', 'personales_jorge'),
    # Infraestructura vía Cristian (paga Render y otras cuentas)
    ('AGUILERA GONZALEZ CRISTIAN', 'infraestructura'),
    ('CRISTIAN AGUILERA', 'infraestructura'),
    # Servicios
    ('CRELL', 'energia_electrica'),
    ('MOVISTAR', 'servicios_basicos'),
    ('BCI SEGUROS', 'seguros'),
    # Operación
    ('EXPRESS PUE', 'insumos'),
    ('EXPRESS PUERTO', 'insumos'),
    ('JUMBO', 'insumos'),
    ('TODO ENVASE', 'insumos'),
    ('INSUMOS SUR', 'insumos'),
    ('TUR-BUS', 'transporte_fletes'),
    ('CRUZ DEL SU', 'transporte_fletes'),
    # Impuestos
    ('MUNICIPALIDAD', 'impuestos'),
]


def clasificar_por_reglas(descripcion):
    """Categoría según las reglas, o None si ninguna calza (queda a mano)."""
    d = (descripcion or '').upper()
    for patron, categoria in REGLAS:
        if patron in d:
            return categoria
    return None
