#!/usr/bin/env python
"""
Script para actualizar las imágenes de las experiencias GiftCard

Este script actualiza el campo 'imagen' de cada experiencia con una
imagen placeholder. Luego puedes reemplazarlas desde el admin.

Uso:
    python actualizar_imagenes_giftcard.py

IMPORTANTE:
- Este script usa imágenes placeholder temporales
- Para producción, sube imágenes reales desde el admin Django
- Recomendación: Fotos de 800x600px en formato JPG
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import GiftCardExperiencia

def actualizar_imagenes_placeholder():
    """
    Actualiza las experiencias con URLs de imágenes placeholder
    """

    print("=" * 70)
    print("🖼️  Actualización de Imágenes GiftCard Experiencias")
    print("=" * 70)
    print()

    # Mapeo de experiencias a imágenes placeholder de Unsplash
    # Estas son URLs públicas de imágenes libres de derechos
    imagenes_placeholder = {
        'tinas': 'giftcards/experiencias/tinas_placeholder.jpg',
        'tinas_masajes_semana': 'giftcards/experiencias/tinas_masajes_placeholder.jpg',
        'tinas_masajes_finde': 'giftcards/experiencias/tinas_masajes_finde_placeholder.jpg',
        'pack_4_personas': 'giftcards/experiencias/pack_4_personas_placeholder.jpg',
        'pack_6_personas': 'giftcards/experiencias/pack_6_personas_placeholder.jpg',
        'masaje_piedras': 'giftcards/experiencias/masaje_piedras_placeholder.jpg',
        'masaje_deportivo': 'giftcards/experiencias/masaje_deportivo_placeholder.jpg',
        'masaje_pareja': 'giftcards/experiencias/masaje_pareja_placeholder.jpg',
        'drenaje_linfatico': 'giftcards/experiencias/drenaje_linfatico_placeholder.jpg',
        'alojamiento_semana': 'giftcards/experiencias/alojamiento_placeholder.jpg',
        'alojamiento_finde': 'giftcards/experiencias/alojamiento_finde_placeholder.jpg',
        'alojamiento_romantico': 'giftcards/experiencias/alojamiento_romantico_placeholder.jpg',
        'tina_cumpleanos': 'giftcards/experiencias/tina_cumpleanos_placeholder.jpg',
        'tina_celebracion': 'giftcards/experiencias/tina_celebracion_placeholder.jpg',
        'monto_libre': 'giftcards/experiencias/monto_libre_placeholder.jpg',
    }

    experiencias = GiftCardExperiencia.objects.all()

    if not experiencias.exists():
        print("⚠️  No se encontraron experiencias en la base de datos")
        print("   Ejecuta primero: python poblar_experiencias_giftcard.py")
        return

    print(f"📦 Encontradas {experiencias.count()} experiencias")
    print()
    print("⚠️  NOTA: Este script usa rutas de imágenes placeholder")
    print("   Para agregar las imágenes REALES:")
    print("   1. Ve al admin: /admin/ventas/giftcardexperiencia/")
    print("   2. Edita cada experiencia")
    print("   3. Sube una foto real (800x600px recomendado)")
    print()
    print("-" * 70)

    actualizadas = 0
    sin_cambios = 0

    for exp in experiencias:
        imagen_path = imagenes_placeholder.get(exp.id_experiencia, '')

        if not imagen_path:
            print(f"⏭️  {exp.id_experiencia}: Sin imagen configurada")
            sin_cambios += 1
            continue

        # Solo actualizar si no tiene imagen o tiene placeholder anterior
        if not exp.imagen or 'placeholder' in str(exp.imagen):
            exp.imagen = imagen_path
            exp.save()
            print(f"✅ {exp.id_experiencia}: Actualizada → {imagen_path}")
            actualizadas += 1
        else:
            print(f"⏭️  {exp.id_experiencia}: Ya tiene imagen ({exp.imagen})")
            sin_cambios += 1

    print()
    print("=" * 70)
    print(f"🎉 Proceso completado")
    print("=" * 70)
    print(f"✅ Actualizadas: {actualizadas}")
    print(f"⏭️  Sin cambios: {sin_cambios}")
    print()

    if actualizadas > 0:
        print("📋 IMPORTANTE: Las imágenes placeholder NO existen físicamente")
        print("   Para ver imágenes reales en los PDFs:")
        print()
        print("   OPCIÓN 1 - Subir desde el Admin (RECOMENDADO):")
        print("   1. Ve a: https://www.aremko.cl/admin/ventas/giftcardexperiencia/")
        print("   2. Haz clic en cada experiencia")
        print("   3. En el campo 'Imagen', haz clic en 'Examinar' y sube la foto")
        print("   4. Guarda")
        print()
        print("   OPCIÓN 2 - Subir por SFTP/SSH:")
        print("   1. Conecta a Render via SSH")
        print("   2. Sube las fotos a: /app/media/giftcards/experiencias/")
        print("   3. Asegúrate que los nombres coincidan con los placeholder")
        print()
        print("   TAMAÑOS RECOMENDADOS:")
        print("   - Resolución: 800x600px o mayor")
        print("   - Formato: JPG (mejor rendimiento)")
        print("   - Peso: < 500KB por imagen")
        print()

if __name__ == '__main__':
    actualizar_imagenes_placeholder()
