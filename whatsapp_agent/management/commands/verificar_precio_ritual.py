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

# El objetivo real depende del día (dom-jue vs vie-sáb); lo entrega disponibilidad_ritual.


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

        # El desayuno YA está incorporado en el precio de la cabaña (Jorge, 2026-06-24):
        # NO se suma como línea aparte (sería doble conteo). Solo cabaña + tina + masaje.
        for clave, pers in (('cabana', personas), ('tina', personas), ('masaje', personas)):
            comp = it.get(clave) or {}
            s = _serv(comp.get('servicio_id'))
            if not s:
                self.stdout.write(self.style.ERROR(f'  {clave}: servicio no encontrado'))
                continue
            pb = int(s.precio_base)
            sub = pb * pers
            suma += sub
            etq = clave.capitalize() + (' (incluye desayuno)' if clave == 'cabana' else '')
            filas.append((f'{etq}: {s.nombre}', pb, pers, sub))

        for nombre, pb, pers, sub in filas:
            self.stdout.write(f'  {nombre:<45} ${pb:>8,} × {pers} = ${sub:>9,}')

        # Informativo: si todavía existe un servicio "Desayuno X" con precio > 0, avisar
        # (con el cambio de Jorge debería estar en $0 o despublicado para no duplicar).
        desayuno = it.get('desayuno')
        if desayuno and int(desayuno.get('precio_total', 0)) > 0:
            self.stdout.write(self.style.WARNING(
                f'  ⚠️  Ojo: existe "{desayuno.get("nombre")}" con valor '
                f'${int(desayuno["precio_total"]):,} aparte. Como el desayuno ya está en la '
                'cabaña, NO se suma aquí; revisar que no se cuele en otra parte.'))

        descuento = r.get('descuento', 0)
        es_torre = r.get('es_torre')
        es_hidro = r.get('es_hidromasaje')
        es_domjue = r.get('es_domjue')
        objetivo = r.get('precio_total', 0)   # objetivo del día (210k dom-jue / 240k vie-sáb)
        self.stdout.write('  ' + '-' * 70)
        self.stdout.write(f'  {"Suma componentes":<45} {"":>14} = ${suma:>9,}')
        if descuento:
            motivos = []
            if es_domjue:
                motivos.append('domingo a jueves')
            if es_torre:
                motivos.append('cabaña Torre')
            if es_hidro:
                motivos.append('tina hidromasaje')
            self.stdout.write(self.style.WARNING(
                f'  {"Descuento (" + ", ".join(motivos) + ")":<45} {"":>14} = -${descuento:>8,}'))
        final = suma - descuento
        self.stdout.write('  ' + '=' * 70)

        dia_txt = 'domingo a jueves' if es_domjue else 'viernes/sábado'
        ok = final == objetivo
        estilo = self.style.SUCCESS if ok else self.style.ERROR
        marca = f'✅ OK ({dia_txt})' if ok else f'❌ DEBERÍA SER ${objetivo:,}'
        self.stdout.write(estilo(f'  {"TOTAL RITUAL":<45} {"":>14} = ${final:>9,}   {marca}'))

        if not ok:
            self.stdout.write(self.style.ERROR(
                f'\n  ⚠️  Descuadre de ${final - objetivo:+,}. Revisar precio_base de los '
                'componentes o la lógica de descuento.'))
        self.stdout.write('')
