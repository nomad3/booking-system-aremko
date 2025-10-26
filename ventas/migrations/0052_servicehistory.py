# Generated migration for ServiceHistory model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0051_advanced_email_campaigns'),
    ]

    operations = [
        migrations.RunSQL(
            # Create table
            sql="""
                CREATE TABLE IF NOT EXISTS crm_service_history (
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

                CREATE INDEX IF NOT EXISTS idx_crm_service_history_cliente
                    ON crm_service_history(cliente_id);
                CREATE INDEX IF NOT EXISTS idx_crm_service_history_date
                    ON crm_service_history(service_date);
            """,
            # Reverse (drop table)
            reverse_sql="""
                DROP TABLE IF EXISTS crm_service_history CASCADE;
            """
        ),
    ]
