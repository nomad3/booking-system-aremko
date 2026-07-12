# -*- coding: utf-8 -*-
# Migración escrita a mano (NO con makemigrations sobre ventas) — mismo criterio
# drift-safe de conciliacion/0002: CreateModel puro en la app aislada facturacion.
# Las FK a ventas (Pago, VentaReserva) solo agregan tablas nuevas; ventas no cambia.
import django.db.models.deletion
from django.db import migrations, models

import facturacion.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('ventas', '0131_masajeslandingconfig_video_recorrido'),
    ]

    operations = [
        migrations.CreateModel(
            name='MedioPago',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(help_text='Debe calzar EXACTO con Pago.metodo_pago (ventas).', max_length=100, unique=True)),
                ('nombre', models.CharField(max_length=150)),
                ('genera_boleta', models.BooleanField(db_index=True, default=False, help_text='ON: cada pago con este medio genera boleta electrónica. OFF: el recaudador informa al SII (voucher = boleta) o no es plata real.')),
                ('nota', models.CharField(blank=True, default='', max_length=255)),
                ('actualizado_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Medio de pago (boleteo)',
                'verbose_name_plural': 'Medios de pago (boleteo)',
                'ordering': ['-genera_boleta', 'codigo'],
            },
        ),
        migrations.CreateModel(
            name='ConfiguracionFacturacion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ambiente', models.CharField(choices=[('simulado', 'Simulado (sin API, para probar la plomería)'), ('certificacion', 'Certificación SII (set de pruebas)'), ('produccion', 'Producción SII')], default='simulado', max_length=20)),
                ('emision_automatica', models.BooleanField(default=False, help_text='F2: al registrarse un pago boleteable se encola la emisión sola. En F1 déjalo apagado (emisión solo manual desde el admin).')),
                ('rut_emisor', models.CharField(blank=True, default='', help_text='RUT de la empresa, con guión y dígito verificador (ej: 76123456-7).', max_length=12)),
                ('razon_social', models.CharField(blank=True, default='', max_length=100)),
                ('giro_boleta', models.CharField(blank=True, default='', help_text='Glosa corta del giro para la boleta (máx 80).', max_length=80)),
                ('direccion', models.CharField(blank=True, default='', max_length=70)),
                ('comuna', models.CharField(blank=True, default='Puerto Varas', max_length=20)),
                ('indicador_servicio', models.PositiveSmallIntegerField(default=3, help_text='3 = ventas y servicios (boleta). No cambiar sin razón.')),
                ('rut_firmante', models.CharField(blank=True, default='', help_text='RUT del dueño del certificado digital (representante legal), con guión.', max_length=12)),
                ('actualizado_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Configuración de facturación',
                'verbose_name_plural': 'Configuración de facturación',
            },
        ),
        migrations.CreateModel(
            name='RangoFolios',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo_dte', models.PositiveSmallIntegerField(db_index=True, default=39)),
                ('ambiente', models.CharField(choices=[('certificacion', 'Certificación SII (set de pruebas)'), ('produccion', 'Producción SII')], max_length=20)),
                ('folio_desde', models.PositiveIntegerField()),
                ('folio_hasta', models.PositiveIntegerField()),
                ('folio_siguiente', models.PositiveIntegerField(help_text='Próximo folio a usar. Se avanza solo; no editar a mano salvo rescate.')),
                ('caf_xml', models.TextField(help_text='Contenido íntegro del archivo CAF (.xml) del SII.')),
                ('activo', models.BooleanField(db_index=True, default=True)),
                ('creado_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Rango de folios (CAF)',
                'verbose_name_plural': 'Rangos de folios (CAF)',
                'ordering': ['tipo_dte', 'folio_desde'],
            },
        ),
        migrations.AddConstraint(
            model_name='rangofolios',
            constraint=models.UniqueConstraint(fields=('tipo_dte', 'ambiente', 'folio_desde'), name='unique_caf_por_rango'),
        ),
        migrations.CreateModel(
            name='BoletaElectronica',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo_dte', models.PositiveSmallIntegerField(default=39)),
                ('ambiente', models.CharField(default='simulado', max_length=20)),
                ('folio', models.PositiveIntegerField(blank=True, db_index=True, null=True)),
                ('monto_total', models.DecimalField(decimal_places=0, max_digits=10)),
                ('monto_neto', models.DecimalField(decimal_places=0, max_digits=10)),
                ('monto_iva', models.DecimalField(decimal_places=0, max_digits=10)),
                ('glosa', models.CharField(blank=True, default='', max_length=200)),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente'), ('simulada', 'Simulada (sin valor tributario)'), ('generada', 'Generada y timbrada'), ('enviada', 'Enviada al SII'), ('aceptada', 'Aceptada por el SII'), ('rechazada', 'Rechazada por el SII'), ('error', 'Error de emisión'), ('anulada', 'Anulada (nota de crédito)')], db_index=True, default='pendiente', max_length=20)),
                ('track_id', models.CharField(blank=True, default='', max_length=60)),
                ('xml_dte', models.TextField(blank=True, default='')),
                ('error_mensaje', models.TextField(blank=True, default='')),
                ('intentos', models.PositiveSmallIntegerField(default=0)),
                ('token_consulta', models.CharField(default=facturacion.models.nuevo_token_consulta, help_text='Token de la página pública de verificación.', max_length=32, unique=True)),
                ('creada_at', models.DateTimeField(auto_now_add=True)),
                ('emitida_at', models.DateTimeField(blank=True, null=True)),
                ('actualizada_at', models.DateTimeField(auto_now=True)),
                ('pago', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='boleta_electronica', to='ventas.pago')),
                ('venta_reserva', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='boletas_electronicas', to='ventas.ventareserva')),
            ],
            options={
                'verbose_name': 'Boleta electrónica',
                'verbose_name_plural': 'Boletas electrónicas',
                'ordering': ['-creada_at'],
            },
        ),
    ]
