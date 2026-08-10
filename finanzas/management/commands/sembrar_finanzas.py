# -*- coding: utf-8 -*-
"""Siembra las cuentas financieras y el plan de cuentas mínimo (P-22 F1).

Idempotente: corre las veces que sea; actualiza nombres/notas sin duplicar.
El mapa de cuentas sale del levantamiento del 2026-08-06/08 (cuatro casillas de
correo + cartola en línea de BancoEstado): tres cuentas de dinero, efectivo,
la tarjeta de crédito y la billetera Mach.
"""
from django.core.management.base import BaseCommand

CUENTAS = [
    # (clave, nombre, tipo, notas)
    ('mercado_pago', 'Mercado Pago', 'pasarela',
     'Recauda ventas web y links de pago; paga trabajadores; barre saldo a Scotiabank. '
     'Verificable por API.'),
    ('bancoestado', 'BancoEstado Chequera Electrónica', 'banco',
     'Recibe las liquidaciones de Flow y SumUp (netas de comisión). También paga. '
     'Cartola por correo y en línea, con botón Exportar (confirmado 2026-08-08). '
     'SumUp declara depositar acá (dato de Jorge 2026-08-08).'),
    ('scotiabank', 'Scotiabank', 'banco',
     'Recibe barridos de MP y transferencias de clientes antiguos (SIN aviso por correo: '
     'los abonos entrantes solo se ven en cartola). Paga sueldos, SII y contador.'),
    ('efectivo', 'Efectivo (caja)', 'efectivo',
     'Solo lo respalda el arqueo físico.'),
    ('visa_2936', 'Visa crédito ••••2936', 'tarjeta_credito',
     'Paga Google Ads, Meta, SendGrid, Anthropic, OpenRouter y más. '
     'Siete rechazos entre jun y ago 2026 — punto único de falla.'),
    ('mach', 'Mach y otros medios', 'billetera',
     'Pagos sueltos (ej. Movistar pagado vía Mach).'),
    ('sumup_transito', 'SumUp (en tránsito)', 'pasarela',
     'Cuenta puente: las comisiones SumUp (API) viven acá — suman al gasto '
     'del mes pero NO tocan el flujo de caja (el neto ya llega a BancoEstado '
     'por cartola). Saldo pendiente visible en el panel SumUp.'),
    # F7 (2026-08-09): cuentas personales puente — mezclan gastos de la
    # empresa con personales. FUERA del flujo de caja (no son caja de
    # Aremko); sus gastos sí clasifican al plan de cuentas.
    ('scotiabank_alda', 'Scotiabank Alda (personal)', 'banco',
     'Cuenta corriente personal de Alda Toloza (99-00138-96). Recibe '
     'retiros desde MP/BancoEstado (se convierten en traspaso al calzar '
     'con su cartola BSA.dat) y paga tarjeta, seguros e impuestos de '
     'Aremko (vale vista). Cartola: BSA.dat de Scotia Connect.'),
    ('cuentarut_jorge', 'CuentaRUT Jorge (personal)', 'banco',
     'CuentaRUT personal de Jorge. Canaliza el presupuesto de Martín '
     '($300k/mes) y gastos mixtos. Formato de cartola pendiente de sondear.'),
    # F7c: las tarjetas de Alda son cuentas propias, como la Visa de Aremko.
    # Sus COMPRAS son el gasto real (con detalle de comercio); el pago de la
    # tarjeta desde su cuenta corriente es un TRASPASO, no un gasto — contar
    # las dos cosas sería el doble conteo que advirtió Jorge.
    ('tarjeta_alda_1', 'Tarjeta Alda 1 (Scotiabank)', 'tarjeta_credito',
     'Tarjeta de crédito de Alda usada para gastos de Aremko y personales. '
     'Se carga el PDF del portal en /finanzas/cargar-cartola/ eligiendo la '
     'tarjeta (el archivo no dice cuál es). Renombrar con los últimos 4 '
     'dígitos cuando se sepan.'),
    ('tarjeta_alda_2', 'Tarjeta Alda 2 (Scotiabank)', 'tarjeta_credito',
     'Segunda tarjeta de crédito de Alda. Mismo tratamiento que la primera.'),
]

CATEGORIAS = [
    # (clave, nombre, clase, orden)
    ('remuneraciones', 'Remuneraciones y pagos a personas', 'gasto', 10),
    ('imposiciones', 'Imposiciones (Previred)', 'gasto', 20),
    ('impuestos', 'Impuestos (SII)', 'gasto', 30),
    ('insumos', 'Insumos y compras de operación', 'gasto', 40),
    ('publicidad', 'Publicidad (Google/Meta/otros)', 'gasto', 50),
    ('infraestructura', 'Infraestructura web y software', 'gasto', 60),
    ('servicios_basicos', 'Servicios básicos y telecomunicaciones', 'gasto', 70),
    ('seguros', 'Seguros', 'gasto', 80),
    ('comisiones', 'Comisiones de pasarelas', 'gasto', 90),
    ('mantencion', 'Mantención y reparaciones', 'gasto', 100),
    ('contabilidad', 'Contabilidad y asesorías', 'gasto', 110),
    ('por_clasificar', 'Por clasificar', 'gasto', 900),
    ('otros_ingresos', 'Otros ingresos (fuera de reservas)', 'ingreso', 10),
]


class Command(BaseCommand):
    help = 'Crea/actualiza cuentas financieras y categorías del plan de cuentas.'

    def handle(self, *args, **opts):
        from finanzas.models import CategoriaFinanciera, CuentaFinanciera

        creadas = actualizadas = 0
        for clave, nombre, tipo, notas in CUENTAS:
            _, creada = CuentaFinanciera.objects.update_or_create(
                clave=clave, defaults={'nombre': nombre, 'tipo': tipo, 'notas': notas})
            creadas += creada
            actualizadas += (not creada)
        self.stdout.write(f'Cuentas: {creadas} nuevas, {actualizadas} actualizadas')

        creadas = actualizadas = 0
        for clave, nombre, clase, orden in CATEGORIAS:
            _, creada = CategoriaFinanciera.objects.update_or_create(
                clave=clave, defaults={'nombre': nombre, 'clase': clase, 'orden': orden})
            creadas += creada
            actualizadas += (not creada)
        self.stdout.write(f'Categorías: {creadas} nuevas, {actualizadas} actualizadas')
        self.stdout.write(self.style.SUCCESS('Siembra lista.'))
