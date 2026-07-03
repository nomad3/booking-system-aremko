# -*- coding: utf-8 -*-
"""Diagnóstico de solo lectura: ¿existen combos tina+masaje MÁS TARDE que los que
devuelve disponibilidad_pack_tina_masaje() para una fecha dada? (Reportado por
Jorge 2026-07-03: Luna le dijo a un cliente real que las opciones de "Pausa junto
al río" que ya le había dado eran "las últimas disponibles" cuando el admin
muestra varios horarios más tarde libres, tanto en tinas como en masajes.)

No escribe nada en la base de datos.

Uso:
    python manage.py diagnosticar_pausa_mas_tarde 2026-07-04
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Compara lo que devuelve disponibilidad_pack_tina_masaje contra TODOS los slots crudos de tina/masaje."

    def add_arguments(self, parser):
        parser.add_argument('fecha', type=str, help='YYYY-MM-DD')
        parser.add_argument('--personas', type=int, default=2)

    def handle(self, *args, **opts):
        from whatsapp_agent import packs
        from whatsapp_agent.availability import disponibilidad, _parse_fecha

        fecha_str = opts['fecha']
        personas = opts['personas']
        f = _parse_fecha(fecha_str)
        if f is None:
            self.stdout.write(self.style.ERROR(f'Fecha inválida: {fecha_str}'))
            return

        self.stdout.write(f'=== Slots CRUDOS de TINA para {f} (personas={personas}) ===')
        tinas = disponibilidad(f, personas, 'tina').get('servicios', [])
        for t in tinas:
            self.stdout.write(f"  {t['nombre']}: {t.get('slots_libres')}")

        self.stdout.write(f'\n=== Slots CRUDOS de MASAJE para {f} (personas=1, incluir_slots_programa=False) ===')
        masajes = disponibilidad(f, 1, 'masaje').get('servicios', [])
        for m in masajes:
            self.stdout.write(f"  {m['nombre']}: {m.get('slots_libres')}")

        self.stdout.write(f'\n=== Slots CRUDOS de MASAJE para {f} CON incluir_slots_programa=True (para comparar) ===')
        masajes_full = disponibilidad(f, 1, 'masaje', incluir_slots_programa=True).get('servicios', [])
        for m in masajes_full:
            self.stdout.write(f"  {m['nombre']}: {m.get('slots_libres')}")

        self.stdout.write(f'\n=== Resultado de disponibilidad_pack_tina_masaje(fecha={fecha_str}, personas={personas}) ===')
        resultado = packs.disponibilidad_pack_tina_masaje(fecha_str, personas=personas)
        for op in resultado.get('opciones', []):
            self.stdout.write(
                f"  [{op['etiqueta']}] tina={op['tina']['nombre']} {op['tina']['hora']} | "
                f"masaje={op['masaje']['nombre']} {op['masaje']['hora']} | "
                f"total=${op['precio_total']:,} | descuento=${op['descuento_pack']:,}"
            )
        self.stdout.write(f"  nota: {resultado.get('nota')!r}")
        self.stdout.write(f"  nota_upsell: {resultado.get('nota_upsell')!r}")

        # Buscar A MANO todos los combos posibles (tina, masaje) que respeten el buffer
        # de 45 min y no se solapen, para ver si hay alguno MÁS TARDE que lo que devolvió
        # la función real — sin el atajo de "la primera tina que encaje".
        self.stdout.write(f'\n=== TODOS los combos válidos posibles (buffer<=45min, sin solape) ===')
        BUFFER_MAX = 45
        combos = []
        for t in tinas:
            t_dur = t.get('duracion_min') or 0
            for t_slot in (t.get('slots_libres') or []):
                t_ini = packs.hhmm_a_min(t_slot)
                if t_ini is None:
                    continue
                for m in masajes:
                    m_dur = m.get('duracion_min') or 0
                    for m_slot in (m.get('slots_libres') or []):
                        m_ini = packs.hhmm_a_min(m_slot)
                        if m_ini is None:
                            continue
                        if not packs.no_solapan(t_ini, t_dur, m_ini, m_dur):
                            continue
                        gap = packs._gap_min(t_ini, t_dur, m_ini, m_dur)
                        if gap <= BUFFER_MAX:
                            combos.append((max(t_ini, m_ini), t['nombre'], t_slot, m['nombre'], m_slot, gap))
        combos.sort()
        for hora_ref, tn, th, mn, mh, gap in combos:
            self.stdout.write(f"  tina {tn} {th}  +  masaje {mn} {mh}  (gap={gap}min)")
        if not combos:
            self.stdout.write('  (ninguno)')
