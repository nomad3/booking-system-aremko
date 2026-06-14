"""Procesa el feedback editado y genera sugerencias de aprendizaje (H-010 parte 2).

Toma los `AgenteFeedback` con `editado=True` y `procesado=False`, clasifica cada
corrección (borrador vs enviado + catálogo) y crea una `SugerenciaAprendizaje`
pendiente SOLO si es accionable (hecho_catalogo / regla). Lo demás (tono/puntual)
se marca procesado sin generar ruido. No bloquea el inbound (corre por cron/manual).

  python manage.py procesar_aprendizaje              # procesa hasta 50
  python manage.py procesar_aprendizaje --limite 10
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Clasifica el feedback editado y crea sugerencias de aprendizaje pendientes.'

    def add_arguments(self, parser):
        parser.add_argument('--limite', type=int, default=50)

    def handle(self, *args, **opts):
        from whatsapp_agent.aprendizaje import procesar_pendientes

        res = procesar_pendientes(opts['limite'])
        if not res['procesados'] and not res['errores']:
            self.stdout.write(self.style.WARNING('No hay feedback editado sin procesar.'))
            return
        for d in res['detalle']:
            if d.get('estado') == 'error':
                self.stdout.write(self.style.ERROR(
                    f'  fb#{d["feedback_id"]}: error ({d["error"]}) — se reintentará'))
            elif d.get('texto'):
                self.stdout.write(self.style.SUCCESS(f'  fb#{d["feedback_id"]} → {d["tipo"]}: {d["texto"]}'))
            else:
                self.stdout.write(f'  fb#{d["feedback_id"]} → {d["tipo"]} (sin sugerencia)')
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\nProcesados: {res["procesados"]} · Sugerencias creadas: {res["creadas"]} '
            f'· Errores: {res["errores"]}'))
