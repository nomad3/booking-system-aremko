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
        from django.utils import timezone
        from whatsapp_agent.aprendizaje import clasificar, TIPOS_ACCIONABLES
        from whatsapp_agent.agent import get_config
        from whatsapp_agent.models import AgenteFeedback, SugerenciaAprendizaje

        config = get_config()
        pendientes = list(
            AgenteFeedback.objects.filter(editado=True, procesado=False)
            .order_by('created_at')[:max(1, opts['limite'])]
        )
        if not pendientes:
            self.stdout.write(self.style.WARNING('No hay feedback editado sin procesar.'))
            return

        creadas = 0
        for fb in pendientes:
            d = clasificar(config, fb.borrador, fb.enviado)
            if d.get('error'):
                # No marcar procesado: reintentar luego (puede ser caída temporal del LLM).
                self.stdout.write(self.style.ERROR(
                    f'  fb#{fb.id}: error clasificando ({d["error"]}) — se reintentará'))
                continue
            if d['tipo'] in TIPOS_ACCIONABLES:
                SugerenciaAprendizaje.objects.create(
                    feedback=fb, phone=fb.phone, tipo=d['tipo'],
                    texto_propuesto=d['texto_propuesto'], ref_catalogo=d['ref_catalogo'],
                    motivo=d['motivo'], borrador=fb.borrador, enviado=fb.enviado,
                    modelo=d.get('modelo', ''),
                )
                creadas += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  fb#{fb.id} → {d["tipo"]}: {d["texto_propuesto"][:80]}'))
            else:
                self.stdout.write(f'  fb#{fb.id} → {d["tipo"]} (sin sugerencia)')
            fb.procesado = True
            fb.save(update_fields=['procesado'])

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\nProcesados: {len(pendientes)} · Sugerencias creadas: {creadas} · {timezone.now():%H:%M}'))
