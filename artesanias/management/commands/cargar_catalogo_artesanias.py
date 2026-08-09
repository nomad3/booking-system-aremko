# -*- coding: utf-8 -*-
"""Carga inicial del catálogo de artesanías desde el papel (2026-08-09).

Modo LECTURA por defecto; --aplicar escribe. Idempotente por código.
Las vendidas históricas quedan con su venta anotada y, si la reserva
existe en el sistema, enlazada (las muy antiguas ya no existen: el número
queda en notas). También crea el Producto genérico de ventas.
"""
import re
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from . import _catalogo_papel as datos


def _fecha(cruda):
    """'16/06/24' · '13-2-26' · '18/9/25' → date (día primero, siglo 20xx)."""
    m = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$', (cruda or '').strip())
    if not m:
        return None
    d, mes, a = (int(x) for x in m.groups())
    if a < 100:
        a += 2000
    try:
        return date(a, mes, d)
    except ValueError:
        return None


class Command(BaseCommand):
    help = 'Carga las 145 piezas del papel al catálogo (idempotente).'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, **opts):
        from ventas.models import VentaReserva

        from artesanias.models import ArtesaniaPieza, producto_generico

        existentes = set(ArtesaniaPieza.objects.values_list('codigo', flat=True))
        nuevas = [p for p in datos.PIEZAS if p[0] not in existentes]
        por_estado = {}
        for p in nuevas:
            por_estado[p[3]] = por_estado.get(p[3], 0) + 1
        self.stdout.write(f'En el papel: {len(datos.PIEZAS)} piezas · '
                          f'ya cargadas: {len(existentes)} · nuevas: {len(nuevas)}')
        for k, n in sorted(por_estado.items()):
            self.stdout.write(f'  {k:<11} {n:>4}')

        if not opts['aplicar']:
            self.stdout.write(self.style.WARNING(
                'MODO LECTURA. Con --aplicar se cargan las nuevas.'))
            return
        if not nuevas:
            self.stdout.write('Nada nuevo que cargar.')
            return

        ids_reserva = {int(p[6]) for p in nuevas if p[6].isdigit()}
        reservas = {r.id: r for r in VentaReserva.objects.filter(id__in=ids_reserva)}

        with transaction.atomic():
            producto_generico()
            enlazadas = 0
            for (codigo, nombre, precio, estado, v_monto, v_fpago,
                 v_reserva, v_fecha, notas) in nuevas:
                reserva = reservas.get(int(v_reserva)) if v_reserva.isdigit() else None
                if reserva:
                    enlazadas += 1
                nota = notas
                if v_reserva and not reserva:
                    nota = (f'{nota} · reserva papel {v_reserva} (no existe en '
                            f'el sistema)').strip(' ·')
                ArtesaniaPieza.objects.create(
                    codigo=codigo,
                    nombre=nombre or '(sin nombre en papel)',
                    precio=int(precio),
                    estado=estado,
                    venta_reserva=reserva,
                    venta_monto=int(v_monto) if v_monto.isdigit() else None,
                    venta_fecha=_fecha(v_fecha),
                    venta_forma_pago=v_fpago,
                    notas=nota[:255],
                )
        self.stdout.write(self.style.SUCCESS(
            f'Listo: {len(nuevas)} piezas cargadas '
            f'({enlazadas} ventas enlazadas a reservas existentes) y '
            f'producto genérico asegurado.'))
