"""Mide cuántas correcciones de Deborah enseñan algo (solo lectura, no escribe nada).

Encargo PROMPT_JEV_AREMKO.md, etapa 0 (Jorge, 25-09-2026): antes de clasificar nada
con un modelo, contar. Reparte los `AgenteFeedback` de la ventana en:

- sin tocar: el borrador salió tal cual;
- retoque: Luna acertó (el enviado repite una hora o un precio del borrador, o se le
  parece ≥ 0,5): corregir eso no enseña una regla;
- descartado: Deborah escribió otra cosa. Se separa en cortos (< 40 caracteres: «ya»,
  «te llamo», ningún borrador habría ganado) y sustantivos (≥ 40).

Los sustantivos sin procesar son la cohorte que vale la pena clasificar. Medido el
25-09 sobre 90 días: 2.281 sustantivos de 4.839 correcciones.

  python manage.py medir_cohorte_aprendizaje            # últimos 30 días (lo que decidió Jorge)
  python manage.py medir_cohorte_aprendizaje --dias 90
"""
from collections import Counter
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

# Un solo criterio: el mismo que usará el lote (`aprendizaje.es_desacuerdo_sustantivo`).
from whatsapp_agent.aprendizaje import LARGO_MINIMO, PARECIDO_RETOQUE, grupo_de_la_correccion


class Command(BaseCommand):
    help = 'Mide la cohorte de correcciones que vale la pena clasificar (solo lectura).'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=30)

    def handle(self, *args, **opts):
        from whatsapp_agent.models import AgenteFeedback

        dias = max(1, opts['dias'])
        desde = timezone.now() - timedelta(days=dias)
        ventana = AgenteFeedback.objects.filter(created_at__gte=desde)
        total = ventana.count()
        editados = ventana.filter(editado=True)
        n_editados = editados.count()

        grupos, cohorte = Counter(), 0
        for borrador, enviado, procesado in editados.values_list(
                'borrador', 'enviado', 'procesado').iterator():
            g = grupo_de_la_correccion(borrador, enviado)
            grupos[g] += 1
            if g == 'sustantivo' and not procesado:
                cohorte += 1

        retoques = grupos['retoque_cifra'] + grupos['retoque_parecido']
        descartados = grupos['corto'] + grupos['sustantivo']
        salida = self.stdout.write
        salida(f'Ventana: últimos {dias} días (desde {timezone.localtime(desde):%d-%m-%Y})')
        salida(f'Correcciones de Deborah: {total} borradores · {n_editados} editados '
               f'({100 * n_editados / max(total, 1):.1f}%) · '
               f'{editados.filter(procesado=False).count()} editados sin procesar')
        salida(f'  sin tocar    {total - n_editados}')
        salida(f'  retoque      {retoques}  (repite hora o precio: {grupos["retoque_cifra"]} · '
               f'parecido ≥ {PARECIDO_RETOQUE}: {grupos["retoque_parecido"]})')
        salida(f'  descartado   {descartados}  (cortos < {LARGO_MINIMO}: {grupos["corto"]} · '
               f'sustantivos: {grupos["sustantivo"]})')
        if grupos['vacio']:
            salida(f'  vacíos       {grupos["vacio"]}')
        salida(self.style.MIGRATE_HEADING(
            f'Cohorte a clasificar (sustantivos sin procesar): {cohorte}'))
