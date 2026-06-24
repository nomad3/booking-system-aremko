# -*- coding: utf-8 -*-
"""Verifica (SOLO LECTURA) el desglose de precios del Ritual del Río para una fecha.

Replica lo que haría `confirmar_ritual` SIN escribir nada: arma el itinerario con
disponibilidad_ritual, mira el precio_base real de cada componente y muestra el total
para confirmar que el descuento premium lo deja en $240.000 exacto.

Uso:
    python manage.py verificar_precio_ritual                 # próximo miércoles disponible
    python manage.py verificar_precio_ritual --fecha "el próximo miércoles"
    python manage.py verificar_precio_ritual --fecha 2026-07-01
"""
from django.core.management.base import BaseCommand

RITUAL_OBJETIVO = 240000


class Command(BaseCommand):
    help = "Desglose de precios del Ritual del Río para una fecha (solo lectura)."

    def add_arguments(self, parser):
        parser.add_argument('--fecha', type=str, default='el próximo miércoles',
                            help='Texto o YYYY-MM-DD (default: "el próximo miércoles").')

    def handle(self, *args, **opts):
        from ventas.models import Servicio
        from whatsapp_agent.packs import disponibilidad_ritual

        fecha = opts['fecha']
        r = disponibilidad_ritual(fecha)

        if r.get('error'):
            self.stdout.write(self.style.ERROR(f'Error: {r["error"]}'))
            return
        if not r.get('disponible'):
            self.stdout.write(self.style.WARNING(
                f'No disponible para "{fecha}" ({r.get("fecha")}): {r.get("nota")}'))
            return

        it = r['itinerario']
        personas = r.get('personas', 2)
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\nRitual del Río — {r["fecha"]} ({personas} personas)\n'))

        # Cada componente: precio_base real × personas (cabaña/tina/masaje) ; desayuno tal cual.
        filas = []          # (nombre, precio_base, personas, subtotal)
        suma = 0

        def _serv(servicio_id):
            try:
                return Servicio.objects.get(id=servicio_id)
            except Servicio.DoesNotExist:
                return None

        for clave, pers in (('cabana', personas), ('tina', personas), ('masaje', personas)):
            comp = it.get(clave) or {}
            s = _serv(comp.get('servicio_id'))
            if not s:
                self.stdout.write(self.style.ERROR(f'  {clave}: servicio no encontrado'))
                continue
            pb = int(s.precio_base)
            sub = pb * pers
            suma += sub
            filas.append((f'{clave.capitalize()}: {s.nombre}', pb, pers, sub))

        desayuno = it.get('desayuno')
        if desayuno:
            pb = int(desayuno.get('precio_total', 0))
            suma += pb
            filas.append((f'Desayuno: {desayuno.get("nombre")}', pb, 1, pb))

        for nombre, pb, pers, sub in filas:
            self.stdout.write(f'  {nombre:<45} ${pb:>8,} × {pers} = ${sub:>9,}')

        descuento = r.get('descuento', 0)
        es_torre = r.get('es_torre')
        es_hidro = r.get('es_hidromasaje')
        self.stdout.write('  ' + '-' * 70)
        self.stdout.write(f'  {"Suma componentes":<45} {"":>14} = ${suma:>9,}')
        if descuento:
            premium = []
            if es_torre:
                premium.append('cabaña Torre')
            if es_hidro:
                premium.append('tina hidromasaje')
            self.stdout.write(self.style.WARNING(
                f'  {"Descuento premium (" + ", ".join(premium) + ")":<45} {"":>14} = -${descuento:>8,}'))
        final = suma - descuento
        self.stdout.write('  ' + '=' * 70)

        ok = final == RITUAL_OBJETIVO
        estilo = self.style.SUCCESS if ok else self.style.ERROR
        marca = '✅ OK' if ok else f'❌ DEBERÍA SER ${RITUAL_OBJETIVO:,}'
        self.stdout.write(estilo(f'  {"TOTAL RITUAL":<45} {"":>14} = ${final:>9,}   {marca}'))

        if not ok:
            self.stdout.write(self.style.ERROR(
                f'\n  ⚠️  Descuadre de ${final - RITUAL_OBJETIVO:+,}. Revisar precio_base de los '
                'componentes o la lógica de descuento ANTES de construir confirmar_ritual.'))
        self.stdout.write('')
