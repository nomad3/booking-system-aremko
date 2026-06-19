# Generated migration for CarritoReserva (H-029 FASE 2)

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('ventas', '0124_alter_cliente_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='CarritoReserva',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('canal', models.CharField(choices=[('whatsapp', 'WhatsApp'), ('instagram', 'Instagram'), ('messenger', 'Messenger')], help_text='Canal de comunicación', max_length=20)),
                ('external_id', models.CharField(help_text='Teléfono (WA), IGSID (IG), o PSID (Messenger)', max_length=100)),
                ('items', models.JSONField(blank=True, default=list, help_text='Lista de items en el carrito. Cada item es un dict:\n        {\n            "tipo": "servicio" | "producto",\n            "id": int,\n            "nombre": str,\n            "precio_unitario": float,\n            "subtotal": float,\n\n            // Si tipo="servicio":\n            "fecha": "YYYY-MM-DD",\n            "hora": "HH:MM",\n            "cantidad_personas": int,\n\n            // Si tipo="producto":\n            "cantidad": int\n        }')),
                ('subtotal_servicios', models.DecimalField(decimal_places=2, default=0, help_text='Suma de precios de servicios', max_digits=10)),
                ('subtotal_productos', models.DecimalField(decimal_places=2, default=0, help_text='Suma de precios de productos', max_digits=10)),
                ('descuento_combo', models.DecimalField(decimal_places=2, default=0, help_text='Descuento por PackDescuento aplicado', max_digits=10)),
                ('packs_aplicados', models.JSONField(blank=True, default=list, help_text='IDs de packs que se aplicaron: [{"pack_id": 1, "nombre": "...", "descuento": 30000}, ...]')),
                ('total', models.DecimalField(decimal_places=2, default=0, help_text='subtotal_servicios + subtotal_productos - descuento_combo', max_digits=10)),
                ('estado', models.CharField(choices=[('activo', 'Carrito activo'), ('checkout', 'En proceso de checkout'), ('creado', 'Convertido a reserva')], default='activo', help_text='Estado del carrito', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('expires_at', models.DateTimeField(blank=True, help_text='Carrito expira si no hay actividad (ej. 24h sin cambios)', null=True)),
                ('venta_reserva', models.OneToOneField(blank=True, help_text='Reserva creada a partir de este carrito (FASE 2→checkout)', null=True, on_delete=django.db.models.deletion.SET_NULL, to='ventas.ventareserva')),
            ],
            options={
                'db_table': 'carrito_reservas_carrioreserva',
            },
        ),
        migrations.AddIndex(
            model_name='carrioreserva',
            index=models.Index(fields=['canal', 'external_id'], name='carrito_res_canal_external_idx'),
        ),
        migrations.AddIndex(
            model_name='carrioreserva',
            index=models.Index(fields=['estado'], name='carrito_res_estado_idx'),
        ),
        migrations.AddIndex(
            model_name='carrioreserva',
            index=models.Index(fields=['created_at'], name='carrito_res_created_at_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='carrioreserva',
            unique_together={('canal', 'external_id')},
        ),
    ]
