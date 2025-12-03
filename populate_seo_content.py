#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para poblar contenido SEO inicial para las categorías de servicio.
Ejecutar después de aplicar la migración 0065_seocontent.

Uso:
    python populate_seo_content.py
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import CategoriaServicio, SEOContent


def crear_contenido_seo():
    """Crea contenido SEO para cada categoría existente"""

    # Contenido SEO para Tinas Calientes (ID=1)
    tinas_data = {
        'meta_title': 'Tinas Calientes Puerto Varas | Hot Tubs al Aire Libre - Aremko Spa',
        'meta_description': 'Relájate en nuestras tinas calientes al aire libre con vista al lago en Puerto Varas. Sesiones privadas, agua termal y ambiente romántico. ¡Reserva online!',
        'subtitulo_principal': 'Sumérgete en el paraíso de la relajación con vista al Lago Llanquihue',
        'contenido_principal': """
Descubre la experiencia única de nuestras tinas calientes en Aremko Spa Puerto Varas. Ubicadas estratégicamente para ofrecer vistas panorámicas del majestuoso Lago Llanquihue y los volcanes de la región, nuestras tinas calientes son el escape perfecto del estrés diario.

Cada sesión en nuestras tinas está diseñada para brindarte privacidad absoluta y confort máximo. El agua, mantenida a la temperatura perfecta entre 38-40°C, está enriquecida con sales minerales que benefician tu piel y sistema circulatorio. Ya sea que busques un momento romántico en pareja o una experiencia relajante individual, nuestras instalaciones están preparadas para superar tus expectativas.

Complementa tu experiencia con nuestros servicios adicionales como ambientación romántica con velas y pétalos, tabla de quesos y vino premium, o masajes terapéuticos. En Aremko Spa, cada detalle está cuidadosamente pensado para crear momentos inolvidables en el corazón de la Patagonia chilena.
        """,
        'beneficio_1_titulo': 'Relajación Profunda',
        'beneficio_1_descripcion': 'El agua caliente ayuda a relajar los músculos tensos, alivia dolores articulares y reduce significativamente los niveles de estrés y ansiedad.',
        'beneficio_2_titulo': 'Mejora la Circulación',
        'beneficio_2_descripcion': 'La hidroterapia estimula la circulación sanguínea, ayuda a eliminar toxinas y fortalece el sistema inmunológico de manera natural.',
        'beneficio_3_titulo': 'Experiencia Romántica',
        'beneficio_3_descripcion': 'Ambiente privado e íntimo perfecto para parejas, con opciones de decoración especial y servicios personalizados.',
        'faq_1_pregunta': '¿Cuánto tiempo dura una sesión de tina caliente?',
        'faq_1_respuesta': 'Nuestras sesiones estándar tienen una duración de 60 a 90 minutos, tiempo ideal para disfrutar de todos los beneficios de la hidroterapia sin sobre-exposición.',
        'faq_2_pregunta': '¿Las tinas son privadas o compartidas?',
        'faq_2_respuesta': 'Todas nuestras tinas son de uso privado. Cada reserva garantiza total privacidad para ti y tus acompañantes durante toda la sesión.',
        'faq_3_pregunta': '¿Qué debo llevar para mi sesión de tina?',
        'faq_3_respuesta': 'Solo necesitas traer tu traje de baño. Nosotros proporcionamos toallas, batas, sandalias y todos los amenities necesarios para tu comodidad.',
        'faq_4_pregunta': '¿Puedo reservar servicios adicionales con mi tina?',
        'faq_4_respuesta': 'Por supuesto. Ofrecemos paquetes que incluyen masajes, tabla de quesos y vinos, decoración romántica y más. Consulta nuestras opciones al hacer tu reserva.',
        'faq_5_pregunta': '¿Es seguro usar las tinas si tengo condiciones médicas?',
        'faq_5_respuesta': 'Si tienes condiciones cardíacas, presión alta, estás embarazada o tienes otras condiciones médicas, te recomendamos consultar con tu médico antes de usar las tinas calientes.',
        'keywords': 'tinas calientes puerto varas, hot tubs, spa puerto varas, hidroterapia, relajación, tinas románticas, wellness chile'
    }

    # Contenido SEO para Masajes (ID=2)
    masajes_data = {
        'meta_title': 'Masajes Relajantes Puerto Varas | Terapéuticos y Descontracturantes',
        'meta_description': 'Masajes profesionales en Puerto Varas: relajantes, descontracturantes, con piedras calientes y aromaterapia. Terapeutas certificados. Reserva tu sesión online.',
        'subtitulo_principal': 'Terapeutas profesionales dedicados a tu bienestar integral',
        'contenido_principal': """
En Aremko Spa Puerto Varas, nuestros masajes son mucho más que un simple tratamiento: son una experiencia transformadora de bienestar integral. Nuestro equipo de terapeutas profesionales certificados combina técnicas ancestrales con métodos modernos para ofrecerte resultados excepcionales.

Cada sesión de masaje es personalizada según tus necesidades específicas. Ya sea que busques alivio para contracturas musculares, reducción del estrés, o simplemente un momento de relajación profunda, adaptamos la presión, técnica y aceites esenciales para maximizar los beneficios de tu tratamiento.

Utilizamos exclusivamente aceites esenciales orgánicos y productos naturales de la más alta calidad. Nuestras salas de masaje están diseñadas para crear un ambiente de tranquilidad absoluta, con música suave, aromaterapia y temperatura perfecta. Descubre por qué somos el spa preferido en Puerto Varas para quienes buscan excelencia en masajes terapéuticos.
        """,
        'beneficio_1_titulo': 'Alivio del Dolor',
        'beneficio_1_descripcion': 'Técnicas especializadas para tratar contracturas, dolores de espalda, cuello y hombros, brindando alivio inmediato y duradero.',
        'beneficio_2_titulo': 'Reducción del Estrés',
        'beneficio_2_descripcion': 'Los masajes activan el sistema nervioso parasimpático, reduciendo cortisol y promoviendo una sensación profunda de calma y bienestar.',
        'beneficio_3_titulo': 'Mejora del Sueño',
        'beneficio_3_descripcion': 'La relajación profunda obtenida durante el masaje mejora la calidad del sueño y ayuda a regular los ciclos de descanso.',
        'faq_1_pregunta': '¿Qué tipo de masaje es mejor para mí?',
        'faq_1_respuesta': 'Nuestros terapeutas realizan una breve consulta antes de cada sesión para entender tus necesidades y recomendar el tipo de masaje más adecuado, ya sea relajante, descontracturante o terapéutico.',
        'faq_2_pregunta': '¿Cuánto tiempo duran las sesiones de masaje?',
        'faq_2_respuesta': 'Ofrecemos sesiones de 30, 60 y 90 minutos. La duración recomendada depende del tipo de tratamiento y tus objetivos específicos.',
        'faq_3_pregunta': '¿Los masajistas son profesionales certificados?',
        'faq_3_respuesta': 'Sí, todos nuestros terapeutas son profesionales certificados con amplia experiencia y formación continua en diversas técnicas de masaje.',
        'faq_4_pregunta': '¿Puedo elegir el género del terapeuta?',
        'faq_4_respuesta': 'Por supuesto. Puedes indicar tu preferencia al momento de hacer la reserva y haremos lo posible para acomodar tu solicitud según disponibilidad.',
        'faq_5_pregunta': '¿Qué debo hacer antes de mi masaje?',
        'faq_5_respuesta': 'Recomendamos llegar 10 minutos antes, evitar comidas pesadas 2 horas antes, hidratarte bien y comunicar cualquier condición médica o área sensible a tu terapeuta.',
        'keywords': 'masajes puerto varas, masaje relajante, masaje descontracturante, spa masajes, masaje terapéutico, masajistas profesionales'
    }

    # Contenido SEO para Alojamientos (ID=3)
    alojamientos_data = {
        'meta_title': 'Cabañas con Tina Caliente Puerto Varas | Alojamiento Romántico Spa',
        'meta_description': 'Cabañas privadas con tina caliente y vista al lago en Puerto Varas. Escapada romántica perfecta con spa, desayuno y servicios premium. ¡Reserva ahora!',
        'subtitulo_principal': 'Tu refugio privado de lujo con spa en la naturaleza',
        'contenido_principal': """
Vive una experiencia única de alojamiento en nuestras exclusivas cabañas con spa privado en Puerto Varas. Cada cabaña ha sido diseñada para ofrecerte el máximo confort y privacidad, combinando el lujo moderno con la calidez de la arquitectura patagónica tradicional.

Imagina despertar con vista al Lago Llanquihue, disfrutar de un desayuno gourmet en tu terraza privada y terminar el día relajándote en tu tina caliente personal bajo las estrellas. Nuestras cabañas están completamente equipadas con todas las comodidades premium: king size bed, chimenea, kitchenette, Wi-Fi de alta velocidad y, por supuesto, acceso ilimitado a tu propia tina caliente.

Perfectas para lunas de miel, aniversarios o simplemente para reconectar con tu pareja, nuestras cabañas ofrecen el escenario ideal para crear recuerdos inolvidables. Complementa tu estadía con nuestros servicios de spa, masajes en la cabaña y experiencias gastronómicas personalizadas.
        """,
        'beneficio_1_titulo': 'Privacidad Total',
        'beneficio_1_descripcion': 'Cabañas independientes con entrada privada, tina caliente exclusiva y espacios diseñados para garantizar tu intimidad absoluta.',
        'beneficio_2_titulo': 'Experiencia Todo Incluido',
        'beneficio_2_descripcion': 'Desayuno gourmet, acceso ilimitado a la tina, amenities de lujo y servicios de spa disponibles directamente en tu cabaña.',
        'beneficio_3_titulo': 'Ubicación Privilegiada',
        'beneficio_3_descripcion': 'Vistas espectaculares al lago y volcanes, cerca del centro de Puerto Varas pero en un entorno natural tranquilo y romántico.',
        'faq_1_pregunta': '¿Qué incluye el alojamiento en las cabañas?',
        'faq_1_respuesta': 'Incluye desayuno continental, uso ilimitado de la tina caliente privada, Wi-Fi, estacionamiento, amenities de baño premium y leña para la chimenea.',
        'faq_2_pregunta': '¿Las cabañas tienen cocina equipada?',
        'faq_2_respuesta': 'Sí, todas las cabañas cuentan con kitchenette equipada con refrigerador, microondas, cafetera, hervidor y utensilios básicos de cocina.',
        'faq_3_pregunta': '¿Puedo solicitar decoración especial para ocasiones románticas?',
        'faq_3_respuesta': 'Absolutamente. Ofrecemos paquetes románticos con decoración especial, pétalos de rosa, velas, champagne y chocolates. Consulta opciones al reservar.',
        'faq_4_pregunta': '¿A qué hora es el check-in y check-out?',
        'faq_4_respuesta': 'Check-in desde las 15:00 hrs y check-out hasta las 12:00 hrs. Podemos coordinar horarios especiales según disponibilidad.',
        'faq_5_pregunta': '¿Admiten mascotas en las cabañas?',
        'faq_5_respuesta': 'Para mantener los estándares de higiene y considerando posibles alergias de futuros huéspedes, no admitimos mascotas en las cabañas.',
        'faq_6_pregunta': '¿Hay servicio de spa en las cabañas?',
        'faq_6_respuesta': 'Sí, ofrecemos servicio de masajes y tratamientos de spa directamente en tu cabaña. Reserva con anticipación para garantizar disponibilidad.',
        'keywords': 'cabañas puerto varas, alojamiento con tina caliente, cabañas románticas, hotel boutique, spa resort, cabañas con hot tub'
    }

    # Crear o actualizar contenido SEO para cada categoría
    contenidos = {
        1: tinas_data,
        2: masajes_data,
        3: alojamientos_data,
    }

    for categoria_id, data in contenidos.items():
        try:
            categoria = CategoriaServicio.objects.get(id=categoria_id)
            seo_content, created = SEOContent.objects.update_or_create(
                categoria=categoria,
                defaults=data
            )
            if created:
                print(f"✅ Creado contenido SEO para: {categoria.nombre}")
            else:
                print(f"✅ Actualizado contenido SEO para: {categoria.nombre}")
        except CategoriaServicio.DoesNotExist:
            print(f"⚠️ Categoría con ID {categoria_id} no encontrada")
        except Exception as e:
            print(f"❌ Error procesando categoría {categoria_id}: {str(e)}")


if __name__ == "__main__":
    print("\n🚀 Iniciando población de contenido SEO...")
    print("-" * 50)

    try:
        crear_contenido_seo()
        print("-" * 50)
        print("✅ Proceso completado exitosamente\n")
    except Exception as e:
        print(f"❌ Error durante el proceso: {str(e)}\n")
        sys.exit(1)