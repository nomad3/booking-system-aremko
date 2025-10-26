# Generated migration for ServiceHistory model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0051_advanced_email_campaigns'),
    ]

    operations = [
        # Step 0: Drop table if exists (to ensure clean slate)
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS crm_service_history CASCADE;",
            reverse_sql=migrations.RunSQL.noop
        ),
        # Step 1: Create table with correct structure
        migrations.RunSQL(
            sql="""
                CREATE TABLE crm_service_history (
                    id SERIAL PRIMARY KEY,
                    cliente_id INTEGER NOT NULL REFERENCES ventas_cliente(id) ON DELETE CASCADE,
                    reserva_id VARCHAR(50) DEFAULT '',
                    service_type VARCHAR(100) NOT NULL,
                    service_name VARCHAR(200) NOT NULL,
                    service_date DATE NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    price_paid NUMERIC(12, 2) NOT NULL,
                    season VARCHAR(50) DEFAULT '',
                    year INTEGER
                );
            """,
            reverse_sql="DROP TABLE IF EXISTS crm_service_history CASCADE;"
        ),
        # Step 2: Create index on cliente_id
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS idx_crm_service_history_cliente
                    ON crm_service_history(cliente_id);
            """,
            reverse_sql="DROP INDEX IF EXISTS idx_crm_service_history_cliente;"
        ),
        # Step 3: Create index on service_date
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS idx_crm_service_history_date
                    ON crm_service_history(service_date);
            """,
            reverse_sql="DROP INDEX IF EXISTS idx_crm_service_history_date;"
        ),
    ]
