# -*- coding: utf-8 -*-
"""Carga histórica jun-ago 2026 al registro financiero (P-22 F1).

Modo LECTURA por defecto: muestra qué cargaría y no escribe nada. Con --aplicar
escribe. Idempotente por `referencia` (hist:<dataset>:<i>): correrlo dos veces
no duplica ni una fila.

Clasificación aplicada (validada con Jorge el 2026-08-08):
- Transferencias MP a "Aremko Spa Scotiabank" → TRASPASO (dos piernas enlazadas,
  suma cero). No son gasto: es la misma plata cambiando de bolsillo.
- Transferencias MP a personas → remuneraciones ("esas son transferencias
  reales, pagos a trabajadores"); "Insumos Sur" → insumos.
- Scotiabank: el pago SII ($1.956.770, 20-jul) → impuestos; el resto entra en
  "por clasificar" con fecha estimada (el correo solo dio el mes). Reclasificar
  es trabajo de la jornada P-22, en el admin.
- Ads → publicidad (Visa ••••2936). Infra → infraestructura/servicios básicos.
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from . import _datos_historicos_2026 as datos

TRASPASO_INTERNO = 'Aremko Spa Scotiabank'
SII_MONTO, SII_FECHA = 1956770, date(2026, 7, 20)


def _fecha(s):
    a, m, d = (int(x) for x in s.split('-'))
    return date(a, m, d)


class Command(BaseCommand):
    help = 'Carga los movimientos históricos jun-ago 2026 minados del correo.'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true',
                            help='Escribe. Sin esto, solo informa.')
        # Decisión de Jorge 2026-08-08: partir de JULIO, el primer mes completo
        # y que se recuerda. Los datos de mayo/junio quedan en _datos_historicos
        # por si algún día se quiere mirar atrás, pero no se cargan: reclasificar
        # gastos que nadie recuerda es adivinar, no ordenar.
        parser.add_argument('--desde', default='2026-07-01',
                            help='No cargar movimientos anteriores a esta fecha (AAAA-MM-DD).')

    def handle(self, *args, **opts):
        from finanzas.models import (CategoriaFinanciera, CuentaFinanciera,
                                     MovimientoFinanciero)

        try:
            cuentas = {c.clave: c for c in CuentaFinanciera.objects.all()}
            cats = {c.clave: c for c in CategoriaFinanciera.objects.all()}
            mp, scotia = cuentas['mercado_pago'], cuentas['scotiabank']
            visa = cuentas['visa_2936']
        except KeyError as e:
            self.stderr.write(f'Falta la cuenta/categoría {e}. Correr antes: '
                              'python manage.py sembrar_finanzas')
            return

        planes = []   # (referencia, dict con kwargs) — se decide TODO antes de escribir

        # ── Egresos y traspasos desde Mercado Pago ──────────────────────────
        for i, (f, monto, benef) in enumerate(datos.MP_EGRESOS):
            fch = _fecha(f)
            if benef == TRASPASO_INTERNO:
                planes.append((f'hist:mp:{i}:sale', dict(
                    fecha=fch, cuenta=mp, clase='traspaso', sentido='sale',
                    monto=monto, descripcion='Barrido MP → Scotiabank',
                    fuente='correo')))
                planes.append((f'hist:mp:{i}:entra', dict(
                    fecha=fch, cuenta=scotia, clase='traspaso', sentido='entra',
                    monto=monto, descripcion='Barrido MP → Scotiabank',
                    fuente='correo', _par=f'hist:mp:{i}:sale')))
            else:
                cat = cats['insumos'] if benef == 'Insumos Sur' else cats['remuneraciones']
                planes.append((f'hist:mp:{i}', dict(
                    fecha=fch, cuenta=mp, clase='gasto', sentido='sale',
                    monto=monto, categoria=cat,
                    descripcion=f'Transferencia MP a {benef}', fuente='correo')))

        # ── Egresos Scotiabank (mes-nivel, salvo el SII) ────────────────────
        for i, (mes, monto) in enumerate(datos.SCOTIABANK_EGRESOS):
            anio, m = (int(x) for x in mes.split('-'))
            if monto == SII_MONTO and (anio, m) == (SII_FECHA.year, SII_FECHA.month):
                planes.append((f'hist:scotia:{i}', dict(
                    fecha=SII_FECHA, cuenta=scotia, clase='gasto', sentido='sale',
                    monto=monto, categoria=cats['impuestos'],
                    descripcion='Pago SII (botón de pago Scotiabank)', fuente='correo')))
            else:
                planes.append((f'hist:scotia:{i}', dict(
                    fecha=date(anio, m, 1), cuenta=scotia, clase='gasto', sentido='sale',
                    monto=monto, categoria=cats['por_clasificar'], fecha_estimada=True,
                    descripcion='Transferencia saliente Scotiabank (día no capturado)',
                    fuente='correo')))

        # ── Publicidad e infraestructura ────────────────────────────────────
        for i, (f, monto, desc) in enumerate(datos.ADS):
            planes.append((f'hist:ads:{i}', dict(
                fecha=_fecha(f), cuenta=visa, clase='gasto', sentido='sale',
                monto=monto, categoria=cats['publicidad'], descripcion=desc,
                fuente='correo')))
        for i, (f, monto, cta, cat, desc) in enumerate(datos.INFRA):
            planes.append((f'hist:infra:{i}', dict(
                fecha=_fecha(f), cuenta=cuentas[cta], clase='gasto', sentido='sale',
                monto=monto, categoria=cats[cat], descripcion=desc, fuente='correo')))

        # ── Corte por fecha (default: julio 2026, primer mes completo) ──────
        desde = _fecha(opts['desde'])
        antes = len(planes)
        planes = [(r, kw) for r, kw in planes if kw['fecha'] >= desde]
        if antes != len(planes):
            self.stdout.write(f'Corte --desde {desde}: {antes - len(planes)} '
                              f'movimientos anteriores quedaron fuera.')

        # ── Resumen previo ──────────────────────────────────────────────────
        existentes = set(MovimientoFinanciero.objects.filter(
            referencia__in=[r for r, _ in planes]).values_list('referencia', flat=True))
        nuevos = [(r, kw) for r, kw in planes if r not in existentes]

        por_clase = {}
        for _, kw in nuevos:
            k = kw['clase']
            por_clase.setdefault(k, [0, 0])
            por_clase[k][0] += int(kw['monto'])
            por_clase[k][1] += 1
        self.stdout.write(f'Planificados: {len(planes)} · ya cargados: {len(existentes)} '
                          f'· nuevos: {len(nuevos)}')
        for k, (m, n) in sorted(por_clase.items()):
            self.stdout.write(f"  {k:<10} {n:>4} movs   ${m:,.0f}".replace(',', '.'))

        if not opts['aplicar']:
            self.stdout.write(self.style.WARNING(
                'MODO LECTURA. Con --aplicar se escriben los nuevos.'))
            return
        if not nuevos:
            self.stdout.write('Nada nuevo que cargar.')
            return

        # ── Escritura: primero todos, después se enlazan las piernas ────────
        with transaction.atomic():
            creados = {}
            for ref, kw in nuevos:
                kw = dict(kw)
                kw.pop('_par', None)
                creados[ref] = MovimientoFinanciero.objects.create(referencia=ref, **kw)
            for ref, kw in nuevos:
                par = kw.get('_par')
                if not par:
                    continue
                salida = creados.get(par) or MovimientoFinanciero.objects.get(referencia=par)
                entrada = creados[ref]
                entrada.traspaso_par = salida
                entrada.save(update_fields=['traspaso_par'])
                salida.traspaso_par = entrada
                salida.save(update_fields=['traspaso_par'])

        # Control final: las piernas de traspaso deben sumar cero.
        from django.db.models import Sum
        agg = {r['sentido']: int(r['t'] or 0)
               for r in MovimientoFinanciero.objects.filter(clase='traspaso')
               .values('sentido').annotate(t=Sum('monto'))}
        if agg.get('entra', 0) == agg.get('sale', 0):
            self.stdout.write(self.style.SUCCESS(
                f"Listo: {len(nuevos)} movimientos. Traspasos cuadran "
                f"(${agg.get('entra', 0):,.0f} por lado).".replace(',', '.')))
        else:
            self.stdout.write(self.style.ERROR(
                f'Cargado, pero los traspasos NO cuadran: {agg}. Revisar.'))
