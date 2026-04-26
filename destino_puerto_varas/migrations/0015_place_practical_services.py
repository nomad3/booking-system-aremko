"""Add Place fields para servicios prácticos al turista.

Campos nuevos:
- requires_reservation (bool)
- recommended_visit_duration (char)
- payment_methods (char)
- pet_friendly (bool)
- has_tourist_info (bool)
- nearby_food_options (text)
- parking_details (text)

Drift-safe: solo AddField sobre tabla existente. No depende de modelos no
aplicados. Sin alteraciones a otros campos.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("destino_puerto_varas", "0014_place_entry_fee_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="place",
            name="requires_reservation",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "¿Requiere reservar/comprar entrada anticipada? "
                    "(museos con cupo, tours, etc.)"
                ),
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="recommended_visit_duration",
            field=models.CharField(
                blank=True,
                max_length=80,
                help_text=(
                    "Tiempo recomendado de visita. Ej: '1-2 horas', 'medio día', "
                    "'jornada completa'."
                ),
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="payment_methods",
            field=models.CharField(
                blank=True,
                max_length=200,
                help_text=(
                    "Métodos de pago aceptados. Ej: 'Efectivo, tarjeta, transferencia. "
                    "No acepta dólares'. Relevante en zonas rurales donde a veces es "
                    "solo efectivo."
                ),
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="pet_friendly",
            field=models.BooleanField(
                default=False,
                help_text="¿Acepta mascotas?",
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="has_tourist_info",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "¿Hay centro/oficina de informaciones turísticas "
                    "(Sernatur, municipal, etc.)?"
                ),
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="nearby_food_options",
            field=models.TextField(
                blank=True,
                default="",
                help_text=(
                    "Opciones de comida cercanas si el lugar no tiene restaurante propio. "
                    "Ej: 'Restaurantes a 5 km en Ensenada' o 'Sin opciones cercanas, "
                    "llevar vianda'."
                ),
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="parking_details",
            field=models.TextField(
                blank=True,
                default="",
                help_text=(
                    "Detalle del estacionamiento si has_parking=True. "
                    "Ej: 'Pago $1.500/día' o 'Gratuito, capacidad 30 autos'."
                ),
            ),
        ),
    ]
