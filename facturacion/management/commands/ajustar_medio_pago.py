"""Ajusta UN medio de pago: si se ofrece al cobrar, si boletea, y su nombre.

La siembra no pisa lo que ya existe —a propósito, para no deshacer lo que Jorge
marcó en el admin—, así que reponer un medio ocultado necesita decirlo aquí.

Sin --confirmar solo muestra el antes y el después.

Uso:
  python manage.py ajustar_medio_pago --codigo mercadopagoaremko --visible
  python manage.py ajustar_medio_pago --codigo mercadopagoaremko --visible --confirmar
"""
from django.core.management.base import BaseCommand, CommandError

from facturacion.models import MedioPago


class Command(BaseCommand):
    help = 'Cambia visibilidad / boleteo / nombre de un medio de pago.'

    def add_arguments(self, parser):
        parser.add_argument('--codigo', required=True)
        parser.add_argument('--visible', action='store_true')
        parser.add_argument('--oculto', action='store_true')
        parser.add_argument('--boletea', action='store_true')
        parser.add_argument('--no-boletea', action='store_true')
        parser.add_argument('--nombre', type=str, default='')
        parser.add_argument('--confirmar', action='store_true')

    def handle(self, *args, **o):
        try:
            m = MedioPago.objects.get(codigo=o['codigo'])
        except MedioPago.DoesNotExist:
            raise CommandError(f'No existe el medio «{o["codigo"]}».')

        antes = (m.nombre, m.visible_al_cobrar, m.genera_boleta)
        if o['visible']:
            m.visible_al_cobrar = True
        if o['oculto']:
            m.visible_al_cobrar = False
        if o['boletea']:
            m.genera_boleta = True
        if o['no_boletea']:
            m.genera_boleta = False
        if o['nombre']:
            m.nombre = o['nombre']
        despues = (m.nombre, m.visible_al_cobrar, m.genera_boleta)

        def _pinta(t):
            return (f'nombre «{t[0]}» · '
                    f'{"se ofrece al cobrar" if t[1] else "oculto al cobrar"} · '
                    f'{"BOLETEA" if t[2] else "no boletea"}')

        self.stdout.write(f'  antes:   {_pinta(antes)}')
        self.stdout.write(f'  después: {_pinta(despues)}')
        if antes == despues:
            self.stdout.write('--- nada que cambiar ---')
            return
        if not o['confirmar']:
            self.stdout.write('--- no se guardó (falta --confirmar) ---')
            return
        m.save(update_fields=['nombre', 'visible_al_cobrar', 'genera_boleta'])
        self.stdout.write('--- guardado ---')
