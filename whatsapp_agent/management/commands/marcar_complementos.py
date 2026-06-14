"""Pre-llena los servicios complementarios del agente por heurística (H-011).

Marca como complemento (no se ofrece como principal) los servicios publicados que:
- tienen precio 0 (cortesía, ej. tina fría / Yates), o
- su nombre contiene "niño"/"nino"/"yates", o
- su categoría es "Ambientaciones" (decoraciones).

Por defecto es DRY-RUN (solo muestra). Con --aplicar guarda en la config del agente.
Después se ajusta a mano desde el admin (selector de doble lista).

  python manage.py marcar_complementos            # muestra qué marcaría
  python manage.py marcar_complementos --aplicar   # lo guarda
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Pre-llena los servicios complementarios del agente por heurística (dry-run por defecto).'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true',
                            help='Guarda los cambios (sin esto, solo muestra).')

    def handle(self, *args, **opts):
        from django.db.models import Q
        from ventas.models import Servicio
        from whatsapp_agent.models import WhatsAppAgentConfig

        candidatos = (
            Servicio.objects.filter(publicado_web=True)
            .filter(
                Q(precio_base=0)
                | Q(nombre__icontains='niño') | Q(nombre__icontains='nino')
                | Q(nombre__icontains='yates')
                | Q(categoria__nombre__iexact='Ambientaciones')
            )
            .order_by('categoria__nombre', 'nombre')
        )

        config = WhatsAppAgentConfig.get_solo()
        ya = config.ids_complementarios()

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'— Candidatos a complemento ({candidatos.count()}) —'))
        for s in candidatos:
            marca = '✓ ya marcado' if s.id in ya else '+ nuevo'
            cat = s.categoria.nombre if s.categoria_id else '—'
            self.stdout.write(f'  [{marca}] {s.nombre} (${int(s.precio_base):,} · {cat})'.replace(',', '.'))

        if not opts.get('aplicar'):
            self.stdout.write(self.style.WARNING(
                '\n(DRY-RUN) Nada guardado. Corre con --aplicar para marcarlos.'))
            return

        config.servicios_complementarios.add(*candidatos)
        total = config.servicios_complementarios.count()
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Aplicado. Servicios complementarios marcados en total: {total}. '
            'Ajusta el resto desde el admin (Configuración Agente WhatsApp).'))
