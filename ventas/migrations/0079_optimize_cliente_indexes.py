# Generated manually for performance optimization

from django.db import migrations

class Migration(migrations.Migration):
    """
    Optimización de índices para mejorar rendimiento en búsqueda y creación de clientes.

    Agrega:
    - Índice compuesto para búsquedas combinadas
    - Índice GIN para búsquedas de texto con pg_trgm
    - Índice en created_at para ordenamiento
    """

    dependencies = [
        ('ventas', '0078_add_massage_reservation_models'),
    ]

    operations = [
        # Índice compuesto para búsquedas del admin
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS ventas_cliente_search_idx ON ventas_cliente(nombre, telefono, email);",
            reverse_sql="DROP INDEX IF EXISTS ventas_cliente_search_idx;"
        ),

        # Índice en created_at para ordenamiento
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS ventas_cliente_created_idx ON ventas_cliente(created_at DESC);",
            reverse_sql="DROP INDEX IF EXISTS ventas_cliente_created_idx;"
        ),

        # Índice GIN para búsquedas de texto (requiere extensión pg_trgm)
        migrations.RunSQL(
            """
            CREATE EXTENSION IF NOT EXISTS pg_trgm;
            CREATE INDEX IF NOT EXISTS ventas_cliente_nombre_gin_idx
            ON ventas_cliente USING gin(nombre gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX IF EXISTS ventas_cliente_nombre_gin_idx;"
        ),

        # Índice parcial para clientes con email (mayoría de búsquedas)
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS ventas_cliente_email_partial_idx
            ON ventas_cliente(email)
            WHERE email IS NOT NULL AND email != '';
            """,
            reverse_sql="DROP INDEX IF EXISTS ventas_cliente_email_partial_idx;"
        ),
    ]