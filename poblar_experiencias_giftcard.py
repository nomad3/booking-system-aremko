#!/usr/bin/env python
"""
Script para poblar la tabla GiftCardExperiencia con las 16 experiencias
hardcodeadas actualmente en giftcard_views.py

IMPORTANTE: Las imágenes deben existir en static/images/ o media/giftcards/experiencias/
Por ahora usaremos las rutas existentes en static.

Ejecutar desde Render shell:
python poblar_experiencias_giftcard.py
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import GiftCardExperiencia

def poblar_experiencias():
    """Crea las 16 experiencias en la base de datos"""

    experiencias_data = [
        # ========== GRUPO TINAS ==========
        {
            'id_experiencia': 'tinas',
            'categoria': 'tinas',
            'nombre': 'Tina para 2',
            'descripcion': 'Tinas calientes para dos personas',
            'descripcion_giftcard': 'Tinas calientes para dos personas en tinas con o sin hidromasaje junto al Río Pescado',
            'imagen': 'images/tinas.jpg',
            'monto_fijo': 50000,
            'montos_sugeridos': [],
            'orden': 1
        },
        {
            'id_experiencia': 'tinas_masajes_semana',
            'categoria': 'tinas',
            'nombre': 'Tina + Masajes (Dom-Jue)',
            'descripcion': 'Tina con masajes para dos de domingo a jueves',
            'descripcion_giftcard': 'Tinas calientes + masajes relajantes para dos personas de domingo a jueves',
            'imagen': 'images/tinas_masajes.jpg',
            'monto_fijo': 95000,
            'montos_sugeridos': [],
            'orden': 2
        },
        {
            'id_experiencia': 'tinas_masajes_finde',
            'categoria': 'tinas',
            'nombre': 'Tina + Masajes (Vie-Sáb)',
            'descripcion': 'Tina con masajes para dos viernes o sábado',
            'descripcion_giftcard': 'Tinas calientes + masajes relajantes para dos personas viernes o sábado',
            'imagen': 'images/tinas_masajes.jpg',
            'monto_fijo': 130000,
            'montos_sugeridos': [],
            'orden': 3
        },
        {
            'id_experiencia': 'pack_4_personas',
            'categoria': 'tinas',
            'nombre': 'Pack 4 Personas',
            'descripcion': '4 horas de tinas + masaje para 4 personas',
            'descripcion_giftcard': 'Pack completo para 4 personas: 4 horas de tinas calientes + masajes relajantes',
            'imagen': 'images/tinas_masajes.jpg',
            'monto_fijo': 190000,
            'montos_sugeridos': [],
            'orden': 4
        },
        {
            'id_experiencia': 'pack_6_personas',
            'categoria': 'tinas',
            'nombre': 'Pack 6 Personas',
            'descripcion': '4 horas de tinas + masaje para 6 personas',
            'descripcion_giftcard': 'Pack completo para 6 personas: 4 horas de tinas calientes + masajes relajantes',
            'imagen': 'images/tinas_masajes.jpg',
            'monto_fijo': 285000,
            'montos_sugeridos': [],
            'orden': 5
        },

        # ========== GRUPO SOLO MASAJES ==========
        {
            'id_experiencia': 'masaje_piedras',
            'categoria': 'masajes',
            'nombre': 'Masaje Piedras Calientes',
            'descripcion': 'Masaje con piedras calientes para 1 persona',
            'descripcion_giftcard': 'Masaje con piedras calientes volcánicas para una persona en domos de bienestar',
            'imagen': 'images/masaje_piedras.jpg',
            'monto_fijo': 45000,
            'montos_sugeridos': [],
            'orden': 6
        },
        {
            'id_experiencia': 'masaje_deportivo',
            'categoria': 'masajes',
            'nombre': 'Masaje Deportivo',
            'descripcion': 'Masaje deportivo profesional para 1 persona',
            'descripcion_giftcard': 'Masaje deportivo profesional para una persona, ideal para recuperación muscular',
            'imagen': 'images/masaje_deportivo.jpg',
            'monto_fijo': 45000,
            'montos_sugeridos': [],
            'orden': 7
        },
        {
            'id_experiencia': 'drenaje_linfatico',
            'categoria': 'masajes',
            'nombre': 'Drenaje Linfático',
            'descripcion': 'Drenaje linfático para 1 persona',
            'descripcion_giftcard': 'Sesión de drenaje linfático profesional para una persona',
            'imagen': 'images/drenaje_linfatico.jpg',
            'monto_fijo': 45000,
            'montos_sugeridos': [],
            'orden': 8
        },
        {
            'id_experiencia': 'masaje_pareja',
            'categoria': 'masajes',
            'nombre': 'Masaje para Dos',
            'descripcion': 'Masaje relajante o descontracturante para dos personas',
            'descripcion_giftcard': 'Masaje relajante o descontracturante para dos personas en nuestros domos de bienestar',
            'imagen': 'images/masaje_pareja.jpg',
            'monto_fijo': 80000,
            'montos_sugeridos': [],
            'orden': 9
        },

        # ========== GRUPO ALOJAMIENTOS ==========
        {
            'id_experiencia': 'alojamiento_semana',
            'categoria': 'packs',  # Cambio de 'alojamientos' a 'packs' para usar categorías definidas
            'nombre': 'Alojamiento + Tinas (Dom-Jue)',
            'descripcion': 'Alojamiento para dos con tinas de domingo a jueves',
            'descripcion_giftcard': 'Alojamiento para dos en cabaña + tinas calientes de domingo a jueves',
            'imagen': 'images/alojamiento_tinas.jpg',
            'monto_fijo': 95000,
            'montos_sugeridos': [],
            'orden': 10
        },
        {
            'id_experiencia': 'alojamiento_finde',
            'categoria': 'packs',
            'nombre': 'Alojamiento + Tinas (Vie-Sáb)',
            'descripcion': 'Alojamiento para dos con tinas viernes o sábado',
            'descripcion_giftcard': 'Alojamiento para dos en cabaña + tinas calientes viernes o sábado',
            'imagen': 'images/alojamiento_tinas.jpg',
            'monto_fijo': 140000,
            'montos_sugeridos': [],
            'orden': 11
        },
        {
            'id_experiencia': 'alojamiento_romantico',
            'categoria': 'packs',
            'nombre': 'Paquete Romántico Completo',
            'descripcion': 'Alojamiento + Tinas + Desayuno + Decoración romántica',
            'descripcion_giftcard': 'Alojamiento + Tinas calientes + Desayuno + Decoración romántica en tinas cualquier día de la semana',
            'imagen': 'images/alojamiento_romantico.jpg',
            'monto_fijo': 150000,
            'montos_sugeridos': [],
            'orden': 12
        },

        # ========== GRUPO CELEBRACIONES ==========
        {
            'id_experiencia': 'tina_cumpleanos',
            'categoria': 'packs',  # Cambio de 'celebraciones' a 'packs'
            'nombre': 'Tina + Ambientación Cumpleaños',
            'descripcion': 'Tina más ambientación de cumpleaños para dos',
            'descripcion_giftcard': 'Tinas calientes + ambientación especial de cumpleaños para dos personas',
            'imagen': 'images/tina_cumpleanos.jpg',
            'monto_fijo': 88000,
            'montos_sugeridos': [],
            'orden': 13
        },
        {
            'id_experiencia': 'tina_celebracion',
            'categoria': 'packs',
            'nombre': 'Tina + Celebración Especial',
            'descripcion': 'Tina más celebración especial para dos',
            'descripcion_giftcard': 'Tinas calientes + ambientación para celebración especial para dos personas',
            'imagen': 'images/tina_celebracion.jpg',
            'monto_fijo': 82000,
            'montos_sugeridos': [],
            'orden': 14
        },

        # ========== MONTO LIBRE ==========
        {
            'id_experiencia': 'monto_libre',
            'categoria': 'valor',
            'nombre': 'Monto Libre',
            'descripcion': 'El destinatario elige la experiencia',
            'descripcion_giftcard': 'Vale por el monto indicado para usar en cualquier experiencia de Aremko Spa',
            'imagen': 'images/gift_generic.jpg',
            'monto_fijo': None,  # NULL para indicar que no tiene monto fijo
            'montos_sugeridos': [30000, 50000, 75000, 100000, 150000, 200000],
            'orden': 15
        }
    ]

    print("🎁 Iniciando población de experiencias Gift Card...\n")

    creadas = 0
    actualizadas = 0
    errores = 0

    for exp_data in experiencias_data:
        try:
            exp, created = GiftCardExperiencia.objects.update_or_create(
                id_experiencia=exp_data['id_experiencia'],
                defaults={
                    'categoria': exp_data['categoria'],
                    'nombre': exp_data['nombre'],
                    'descripcion': exp_data['descripcion'],
                    'descripcion_giftcard': exp_data['descripcion_giftcard'],
                    'imagen': exp_data['imagen'],
                    'monto_fijo': exp_data['monto_fijo'],
                    'montos_sugeridos': exp_data['montos_sugeridos'],
                    'orden': exp_data['orden'],
                    'activo': True
                }
            )

            if created:
                print(f"✅ Creada: {exp.nombre} (${exp.monto_fijo:,})" if exp.monto_fijo else f"✅ Creada: {exp.nombre} (Valor variable)")
                creadas += 1
            else:
                print(f"🔄 Actualizada: {exp.nombre}")
                actualizadas += 1

        except Exception as e:
            print(f"❌ Error con {exp_data['nombre']}: {str(e)}")
            errores += 1

    print(f"\n{'='*60}")
    print(f"📊 Resumen:")
    print(f"   • Experiencias creadas: {creadas}")
    print(f"   • Experiencias actualizadas: {actualizadas}")
    print(f"   • Errores: {errores}")
    print(f"   • Total en BD: {GiftCardExperiencia.objects.count()}")
    print(f"{'='*60}\n")

    # Mostrar experiencias por categoría
    print("📋 Experiencias por categoría:")
    for categoria_code, categoria_nombre in GiftCardExperiencia.CATEGORIA_CHOICES:
        count = GiftCardExperiencia.objects.filter(categoria=categoria_code, activo=True).count()
        if count > 0:
            print(f"   • {categoria_nombre}: {count} experiencias")

    print("\n✨ ¡Listo! Las experiencias están en la base de datos.")
    print("⚠️  NOTA: Recuerda que las imágenes deben existir en static/images/")
    print("    Si no existen, súbelas o actualiza las rutas desde el admin.\n")

if __name__ == '__main__':
    poblar_experiencias()
