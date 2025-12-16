#!/usr/bin/env python3
"""
Script para crear contenido SEO para la página de Productos

Ejecutar: python scripts/create_productos_seo.py
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')

import django
django.setup()

from ventas.models import SeoContent

print("\n" + "=" * 80)
print("CREAR CONTENIDO SEO PARA PRODUCTOS")
print("=" * 80)

# Verificar si ya existe
existing = SeoContent.objects.filter(page_type='productos').first()

if existing:
    print("\n⚠️  Ya existe contenido SEO para Productos")
    print(f"   Título: {existing.meta_title}")
    print(f"   Descripción: {existing.meta_description[:100]}...")

    respuesta = input("\n¿Deseas actualizarlo? (s/n): ")
    if respuesta.lower() not in ['s', 'si', 'sí', 'y', 'yes']:
        print("❌ Operación cancelada")
        sys.exit(0)

    seo = existing
    print("\n✏️  Actualizando contenido existente...")
else:
    seo = SeoContent()
    seo.page_type = 'productos'
    print("\n✨ Creando nuevo contenido SEO...")

# Configurar contenido SEO
seo.meta_title = "Productos Gourmet Aremko - Tablas de Queso Artesanales | Puerto Varas"
seo.meta_description = "Descubre nuestros productos gourmet exclusivos en Aremko Spa Puerto Varas. Tablas de queso artesanales, productos locales de la más alta calidad. Consulta por WhatsApp."

# H1
seo.h1_title = "Nuestros Productos Gourmet"

# Contenido principal
seo.main_content = """
Descubre nuestra selección exclusiva de productos gourmet, cuidadosamente elaborados con ingredientes de la más alta calidad de la Región de Los Lagos.

**Tablas de Queso Artesanales**

Nuestras tablas de queso son una experiencia gastronómica única, combinando quesos artesanales locales con mermeladas caseras, frutos secos de la zona y acompañamientos gourmet.

**Productos Locales**

Trabajamos con productores locales de Puerto Varas y la Región de Los Lagos para ofrecerte productos auténticos que reflejan la riqueza culinaria del sur de Chile.
"""

# FAQs
seo.faqs = [
    {
        "pregunta": "¿Cómo puedo comprar los productos?",
        "respuesta": "Puedes consultar disponibilidad y hacer tu pedido directamente por WhatsApp. Haz clic en el botón 'Consultar' junto a cada producto y te contactaremos de inmediato."
    },
    {
        "pregunta": "¿Los productos están disponibles todo el año?",
        "respuesta": "La disponibilidad de nuestros productos puede variar según la temporada y los ingredientes frescos disponibles. Te recomendamos consultar por WhatsApp para confirmar disponibilidad antes de tu visita."
    },
    {
        "pregunta": "¿Puedo personalizar una tabla de queso?",
        "respuesta": "Sí, podemos personalizar nuestras tablas de queso según tus preferencias. Contáctanos por WhatsApp y cuéntanos qué tipo de quesos y acompañamientos prefieres."
    },
    {
        "pregunta": "¿Hacen despacho a domicilio?",
        "respuesta": "Consulta por WhatsApp sobre opciones de despacho en Puerto Varas y alrededores. Las condiciones pueden variar según la ubicación y el pedido."
    }
]

seo.save()

print(f"✅ Contenido SEO creado/actualizado exitosamente!")
print(f"\n📋 Resumen:")
print(f"   Meta Title: {seo.meta_title}")
print(f"   Meta Description: {seo.meta_description}")
print(f"   H1: {seo.h1_title}")
print(f"   FAQs: {len(seo.faqs)} preguntas")

print("\n" + "=" * 80)
print("COMPLETADO")
print("=" * 80)
print("\n✅ Ahora ve al admin y verás 'Productos' en Contenidos SEO")
print("   Puedes editar el contenido desde ahí si lo deseas.\n")
