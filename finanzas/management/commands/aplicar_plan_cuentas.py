# -*- coding: utf-8 -*-
"""Aplica el plan de cuentas de Jorge (2026-08-08): sincroniza categorías con
sus grupos y reclasifica los movimientos existentes según las reglas por
descripción (finanzas/reglas.py).

Modo LECTURA por defecto; con --aplicar escribe. Solo toca movimientos cuya
categoría actual sea «por clasificar» o «remuneraciones» (las transferencias
del correo caían todas ahí antes de conocer quién era quién) — lo asignado a
mano no se pisa.

    python manage.py aplicar_plan_cuentas            # muestra qué haría
    python manage.py aplicar_plan_cuentas --aplicar
"""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from finanzas.reglas import PLAN_CUENTAS, clasificar_por_reglas


class Command(BaseCommand):
    help = 'Sincroniza el plan de cuentas y reclasifica según las reglas.'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, **opts):
        from finanzas.models import CategoriaFinanciera, MovimientoFinanciero

        # ── 1. Sincronizar categorías (crear faltantes, actualizar grupo) ───
        creadas = actualizadas = 0
        for clave, (nombre, clase, grupo) in PLAN_CUENTAS.items():
            cat = CategoriaFinanciera.objects.filter(clave=clave).first()
            if cat is None:
                if opts['aplicar']:
                    CategoriaFinanciera.objects.create(
                        clave=clave, nombre=nombre, clase=clase, grupo=grupo)
                creadas += 1
                self.stdout.write(f'  categoría NUEVA: {clave} → grupo {grupo}')
            elif (cat.nombre, cat.clase, cat.grupo) != (nombre, clase, grupo):
                if opts['aplicar']:
                    cat.nombre, cat.clase, cat.grupo = nombre, clase, grupo
                    cat.save(update_fields=['nombre', 'clase', 'grupo'])
                actualizadas += 1
                self.stdout.write(f'  categoría actualizada: {clave} → grupo {grupo}')
        self.stdout.write(f'Categorías: {creadas} nuevas · {actualizadas} actualizadas')

        # ── 2. Reclasificar movimientos por reglas ──────────────────────────
        objetivo = MovimientoFinanciero.objects.filter(
            clase='gasto',
            categoria__clave__in=('por_clasificar', 'remuneraciones'),
        ).select_related('categoria')

        cambios = Counter()
        planes = []
        for m in objetivo:
            nueva = clasificar_por_reglas(m.descripcion)
            if nueva and nueva != m.categoria.clave:
                planes.append((m, nueva))
                cambios[f'{m.categoria.clave} → {nueva}'] += 1

        for etiqueta, n in sorted(cambios.items()):
            self.stdout.write(f'  {n:>4} movs · {etiqueta}')
        self.stdout.write(f'Reclasificaciones: {len(planes)} de '
                          f'{objetivo.count()} revisados (el resto queda a mano)')

        if not opts['aplicar']:
            self.stdout.write(self.style.WARNING(
                'MODO LECTURA. Con --aplicar se escribe todo lo de arriba.'))
            return

        with transaction.atomic():
            cats = {c.clave: c for c in CategoriaFinanciera.objects.all()}
            for m, nueva in planes:
                m.categoria = cats[nueva]
                m.save(update_fields=['categoria'])
        self.stdout.write(self.style.SUCCESS(
            f'Listo: plan de cuentas aplicado y {len(planes)} movimientos '
            f'reclasificados.'))
