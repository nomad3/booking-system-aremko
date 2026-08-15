from django.db import migrations, models


class Migration(migrations.Migration):
    """Agrega Producto.venta_meson: productos que el personal vende en el mesón
    (espumantes, vinos) sin exponerlos en el link público de comanda del cliente.

    Mismo patrón que 0120: SeparateDatabaseAndState + `ADD COLUMN IF NOT EXISTS`
    para deploy sin downtime (migrate MANUAL en Render). La columna se pre-agrega
    a mano ANTES del push, porque el admin nuevo la LEE en el queryset del
    selector de productos: si no existiera, cada reserva abierta sería un 500.

    Nace en false para todos: Jorge marca a mano los que van al mesón.
    """

    dependencies = [
        ('ventas', '0133_refugio_precio_290000'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='producto',
                    name='venta_meson',
                    field=models.BooleanField(
                        default=False,
                        verbose_name='Venta en Mesón',
                        help_text='Si está marcado, el personal puede agregar este producto a una reserva '
                                  'o comanda desde el admin, sin que aparezca en el menú público del cliente',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE ventas_producto "
                        "ADD COLUMN IF NOT EXISTS venta_meson boolean NOT NULL DEFAULT false;"
                    ),
                    reverse_sql=(
                        "ALTER TABLE ventas_producto DROP COLUMN IF EXISTS venta_meson;"
                    ),
                ),
            ],
        ),
    ]
