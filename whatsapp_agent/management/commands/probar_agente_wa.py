"""Prueba el agente IA de WhatsApp sin enviar nada y sin necesidad de prenderlo.

Genera un borrador (catálogo vivo + LLM reales) para un mensaje de prueba o para
el último entrante real de un teléfono, y lo imprime. Ideal para validar en el
Shell de Render con el número de prueba de Meta antes de exponerlo a clientes.

Ejemplos:
  python manage.py probar_agente_wa --mensaje "Hola, hacen masajes? cuánto cuesta?"
  python manage.py probar_agente_wa --mensaje "Quiero reclamar, pésima atención"
  python manage.py probar_agente_wa --phone +56912345678
"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Genera un borrador de prueba del agente WhatsApp (no envía nada).'

    def add_arguments(self, parser):
        parser.add_argument('--mensaje', type=str, default='',
                            help='Texto del cliente a responder (modo dry-run, sin DB).')
        parser.add_argument('--phone', type=str, default='',
                            help='Usa el último entrante real sin responder de este teléfono.')
        parser.add_argument('--historial', type=str, default='',
                            help='Contexto previo opcional (solo con --mensaje).')

    def handle(self, *args, **opts):
        from whatsapp_agent.agent import (
            _producir_borrador, _historial_texto, _entrante_a_responder,
            _modelo_efectivo, get_config,
        )

        mensaje = (opts.get('mensaje') or '').strip()
        phone = (opts.get('phone') or '').strip()
        historial = opts.get('historial') or ''

        if not mensaje and not phone:
            raise CommandError('Indica --mensaje "texto" o --phone <numero>.')

        config = get_config()
        if phone and not mensaje:
            entrante = _entrante_a_responder(phone)
            if entrante is None:
                raise CommandError(f'No hay entrante de texto sin responder para {phone}.')
            mensaje = entrante.body or ''
            historial = _historial_texto(phone, entrante.timestamp, config.history_window)

        self.stdout.write(self.style.MIGRATE_HEADING('— Config del agente —'))
        self.stdout.write(f'  activo={config.activo} · modo={config.modo} · '
                          f'modelo={_modelo_efectivo(config)} · temp={config.temperature}')
        self.stdout.write(self.style.MIGRATE_HEADING('— Mensaje del cliente —'))
        self.stdout.write(f'  {mensaje!r}')
        if historial.strip():
            self.stdout.write(self.style.MIGRATE_HEADING('— Historial —'))
            self.stdout.write('  ' + historial.replace('\n', '\n  '))

        d = _producir_borrador(config, mensaje, historial)

        self.stdout.write(self.style.MIGRATE_HEADING('— Resultado —'))
        if d['escalar']:
            self.stdout.write(self.style.WARNING(f'  ⚠️  ESCALAR a persona — motivo: {d["motivo"]}'))
        else:
            self.stdout.write(self.style.SUCCESS('  ✨ Borrador sugerido:'))
            self.stdout.write(f'  {d["texto"]}')
        if d['error']:
            self.stdout.write(self.style.ERROR(f'  error: {d["error"]}'))
        self.stdout.write(
            f'  modelo={d["modelo"] or "—"} · tokens in/out={d["input_tokens"]}/{d["output_tokens"]} '
            f'· {d["latency_ms"]} ms'
        )
