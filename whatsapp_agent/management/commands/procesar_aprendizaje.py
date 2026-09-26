"""Procesa el feedback editado y genera sugerencias de aprendizaje (H-010 parte 2).

Toma los `AgenteFeedback` con `editado=True` y `procesado=False`, clasifica cada
corrección (borrador vs enviado + catálogo) y crea una `SugerenciaAprendizaje`
pendiente SOLO si es accionable (hecho_catalogo / regla). Lo demás (tono/puntual)
se marca procesado sin generar ruido. No bloquea el inbound (corre por cron/manual).

  python manage.py procesar_aprendizaje              # procesa hasta 50
  python manage.py procesar_aprendizaje --limite 10

Encargo JEV, etapa 4 — la corrida en seco que Jorge lee antes de procesar nada:

  python manage.py procesar_aprendizaje --solo-sustantivos --dias 30 --en-seco --jev --limite 50

  --solo-sustantivos  solo las correcciones que enseñan algo, las más recientes primero
  --dias N            solo las de los últimos N días
  --en-seco           clasifica e imprime, SIN crear sugerencias y SIN marcar procesado
  --jev               usa Jev aunque el interruptor de la configuración esté apagado

Etapa 5: con el interruptor prendido, el botón de la página Agente IA procesa lo mismo que
`--solo-sustantivos --dias 30`, y los no concluyentes se marcan vistos.
"""

from collections import Counter

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Clasifica el feedback editado y crea sugerencias de aprendizaje pendientes.'

    def add_arguments(self, parser):
        parser.add_argument('--limite', type=int, default=50)
        parser.add_argument('--solo-sustantivos', action='store_true')
        parser.add_argument('--dias', type=int, default=None)
        parser.add_argument('--en-seco', action='store_true')
        parser.add_argument('--jev', action='store_true')

    def handle(self, *args, **opts):
        from whatsapp_agent.aprendizaje import procesar_pendientes

        en_seco = opts['en_seco']
        res = procesar_pendientes(opts['limite'], solo_sustantivos=opts['solo_sustantivos'],
                                  en_seco=en_seco, dias=opts['dias'], forzar_jev=opts['jev'])
        if not res['procesados'] and not res['errores']:
            self.stdout.write(self.style.WARNING('No hay feedback editado sin procesar.'))
            return
        if en_seco:
            self._en_seco(res)
            return
        for d in res['detalle']:
            if d.get('estado') == 'error':
                self.stdout.write(self.style.ERROR(
                    f'  fb#{d["feedback_id"]}: error ({d["error"]}) — se reintentará'))
            elif d.get('estado') == 'no_concluyente':
                self.stdout.write(f'  fb#{d["feedback_id"]}: {d["error"]} — marcada vista')
            elif d.get('texto'):
                self.stdout.write(self.style.SUCCESS(f'  fb#{d["feedback_id"]} → {d["tipo"]}: {d["texto"]}'))
            else:
                self.stdout.write(f'  fb#{d["feedback_id"]} → {d["tipo"]} (sin sugerencia)')
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\nProcesados: {res["procesados"]} · Sugerencias creadas: {res["creadas"]} '
            f'· No concluyentes: {res["no_concluyentes"]} · Errores: {res["errores"]}'))

    def _en_seco(self, res):
        """Una ficha por corrección: qué propuso Luna, qué envió Deborah y qué decidió el
        clasificador. Nada se guardó."""
        escribir = self.stdout.write
        resultados = Counter()
        for d in res['detalle']:
            conf = d.get('confianza')
            conf_txt = f' · confianza {conf:.2f}' if conf is not None else ''
            if d.get('estado') in ('error', 'no_concluyente'):
                resultado = 'NO CONCLUYENTE' if d['estado'] == 'no_concluyente' else 'ERROR'
                detalle = d['error']
            elif d.get('texto'):
                resultado = f'PROPONDRÍA {d["tipo"].upper()}'
                detalle = f'«{d["texto"]}»'
            else:
                resultado = d.get('tipo', '').upper()
                detalle = d.get('motivo', '')
            resultados[resultado.split(' ')[0] if resultado.startswith('PROPONDRÍA') else resultado] += 1
            fecha = timezone.localtime(d['fecha']).strftime('%d-%m') if d.get('fecha') else ''
            escribir(f'fb#{d["feedback_id"]} · {fecha} · {resultado}{conf_txt}')
            escribir(f'   decide: {detalle}')
            escribir(f'   Luna:    {(d.get("borrador") or "").replace(chr(10), " ")}')
            escribir(f'   Deborah: {(d.get("enviado") or "").replace(chr(10), " ")}')
        escribir(self.style.MIGRATE_HEADING(
            f'\nEN SECO (nada se guardó) · {len(res["detalle"])} correcciones · '
            + ' · '.join(f'{k}: {v}' for k, v in resultados.most_common())))
