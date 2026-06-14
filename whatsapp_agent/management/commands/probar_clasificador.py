"""Prueba el clasificador de correcciones (H-010 p2) sin tocar la BD.

Dado un borrador y lo enviado, muestra cómo clasificaría la corrección (tipo +
texto propuesto + destino). Útil para validar el clasificador con casos reales.

  python manage.py probar_clasificador \
    --borrador "La tina Calbuco cuesta $25.000" \
    --enviado  "La tina Calbuco cuesta $25.000 por persona, son $100.000 para 4"
"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Clasifica una corrección (borrador vs enviado) sin guardar nada.'

    def add_arguments(self, parser):
        parser.add_argument('--borrador', type=str, required=True)
        parser.add_argument('--enviado', type=str, required=True)

    def handle(self, *args, **opts):
        from whatsapp_agent.agent import get_config
        from whatsapp_agent.aprendizaje import clasificar

        borrador = opts['borrador']
        enviado = opts['enviado']
        if not borrador.strip() or not enviado.strip():
            raise CommandError('Pasa --borrador y --enviado con texto.')

        d = clasificar(get_config(), borrador, enviado)

        self.stdout.write(self.style.MIGRATE_HEADING('— Borrador → Enviado —'))
        self.stdout.write(f'  borrador: {borrador!r}')
        self.stdout.write(f'  enviado:  {enviado!r}')
        self.stdout.write(self.style.MIGRATE_HEADING('— Clasificación —'))
        if d.get('error'):
            self.stdout.write(self.style.ERROR(f'  error: {d["error"]}'))
            return
        accionable = d['tipo'] in ('hecho_catalogo', 'regla')
        estilo = self.style.SUCCESS if accionable else self.style.WARNING
        self.stdout.write(estilo(f'  tipo: {d["tipo"]}' + ('' if accionable else '  (no genera sugerencia)')))
        if d['texto_propuesto']:
            self.stdout.write(f'  propuesto: {d["texto_propuesto"]}')
        if d['ref_catalogo']:
            self.stdout.write(f'  ref_catalogo: {d["ref_catalogo"]}')
        if d['motivo']:
            self.stdout.write(f'  motivo: {d["motivo"]}')
        self.stdout.write(f'  modelo: {d.get("modelo") or "—"}')
