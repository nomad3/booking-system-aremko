import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Vínculo Proveedor.usuario (OneToOne a auth User) para que cada masajista
    vea/edite solo sus fichas asignadas.

    Mismo patrón que 0116/0117/0120/0121: SeparateDatabaseAndState + ADD COLUMN IF
    NOT EXISTS para deploy seguro/idempotente sin downtime (migrate MANUAL en Render).
    Correr el SQL ANTES (o el migrate lo crea) evita la ventana en que el código
    nuevo consulta la columna inexistente. La OneToOne se respalda con un índice
    UNIQUE (permite múltiples NULL en Postgres).
    """

    dependencies = [
        ('ventas', '0121_scriptwhatsapp_meta_template'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='proveedor',
                    name='usuario',
                    field=models.OneToOneField(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='proveedor',
                        to=settings.AUTH_USER_MODEL,
                        help_text='Usuario de login de este proveedor (para masajistas: ver/editar sus fichas asignadas).',
                        verbose_name='Usuario vinculado',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE ventas_proveedor ADD COLUMN IF NOT EXISTS usuario_id integer NULL;"
                        "CREATE UNIQUE INDEX IF NOT EXISTS ventas_proveedor_usuario_id_key ON ventas_proveedor(usuario_id);"
                    ),
                    reverse_sql=(
                        "DROP INDEX IF EXISTS ventas_proveedor_usuario_id_key;"
                        "ALTER TABLE ventas_proveedor DROP COLUMN IF EXISTS usuario_id;"
                    ),
                ),
            ],
        ),
    ]
