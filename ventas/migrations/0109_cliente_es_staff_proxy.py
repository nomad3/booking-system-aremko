"""
0109_cliente_es_staff_proxy
============================

Agrega campos `es_staff_proxy` (BooleanField, indexed) y
`es_staff_proxy_razon` (CharField) al modelo Cliente.

Contexto:
    Solicitud del agente aremko-cli 2026-05-27 PM: necesitan endpoint
    `POST /clientes/<id>/marcar-staff/` para que el operador desde la
    bandeja pueda marcar instantáneamente un cliente interno (Jorge
    Aguilera dueño, Deborah operadora, Ernesto recepción, etc.) sin
    requerir cambio de settings.py + redeploy.

    Hoy el flujo era: ver cliente staff → pedir update settings → agente
    edita + redeploy → ~30 min. Con el endpoint nuevo: 5 segundos.

    El cron `generar_bandeja_whatsapp_diaria` filtra
    `es_staff_proxy=True` antes de evaluar candidatos. Bloqueante
    permanente sin tocar settings.

Migración trivial: solo AddField sobre 2 columnas. Sin data migration.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0108_quitar_almuerzo_plantillas'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='es_staff_proxy',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    'True si este registro es de personal Aremko o cuenta proxy '
                    'del staff (no cliente real). Excluido de bandeja WhatsApp.'
                ),
            ),
        ),
        migrations.AddField(
            model_name='cliente',
            name='es_staff_proxy_razon',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Por qué se marcó como staff/proxy (auditoría).',
                max_length=200,
            ),
        ),
    ]
