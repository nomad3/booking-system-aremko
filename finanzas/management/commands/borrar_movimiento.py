"""Borra UN movimiento financiero por id, mostrándolo antes.

Para las correcciones puntuales que ningún detector puede decidir solo. El
caso que lo motivó (31-08-2026): cuatro cargos de $208 el mismo día eran las
cuotas 01/12 y 02/12 de un crédito, más una captura repetida de la 01/12 con
las palabras en otro orden — «MERCADOPAGO*AREMKO LAS CONDES TASA» contra
«MERCADOPAGO*AREMKO TASA LAS CONDES». Ninguna es prefijo de la otra, así que
`revisar_duplicados` no las junta, y el monto por sí solo no distingue una
cuota de su copia: hay que leer la glosa.

Sin --confirmar solo muestra. No borra nada que sea parte de un traspaso
calzado: eso deja la otra pierna huérfana y hay que descalzarlo primero.

Uso:
  python manage.py borrar_movimiento --id 831
  python manage.py borrar_movimiento --id 831 --confirmar
"""
from django.core.management.base import BaseCommand, CommandError

from finanzas.models import MovimientoFinanciero


class Command(BaseCommand):
    help = 'Muestra y (con --confirmar) borra un movimiento por id.'

    def add_arguments(self, parser):
        parser.add_argument('--id', type=int, required=True)
        parser.add_argument('--confirmar', action='store_true')

    def handle(self, *args, **o):
        try:
            m = MovimientoFinanciero.objects.select_related(
                'cuenta', 'categoria').get(pk=o['id'])
        except MovimientoFinanciero.DoesNotExist:
            raise CommandError(f'No existe el movimiento #{o["id"]}.')

        monto = f'${int(m.monto):,}'.replace(',', '.')
        self.stdout.write(f'#{m.id} · {m.fecha} · {m.cuenta.nombre}')
        self.stdout.write(f'  {m.clase} {m.sentido} {monto} · '
                          f'{m.categoria.nombre if m.categoria else "sin categoría"}')
        self.stdout.write(f'  glosa: «{m.descripcion}»')
        self.stdout.write(f'  ref:   «{m.referencia}» · fuente {m.fuente}')

        if m.traspaso_par_id:
            raise CommandError(
                f'#{m.id} es parte de un traspaso calzado con '
                f'#{m.traspaso_par_id}: borrarlo dejaría la otra pierna '
                f'huérfana. Primero hay que deshacer el calce.')

        if not o['confirmar']:
            self.stdout.write('--- no se borró (falta --confirmar) ---')
            return

        m.delete()
        self.stdout.write(f'--- BORRADO #{o["id"]} por {monto} ---')
