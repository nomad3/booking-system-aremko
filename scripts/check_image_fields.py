#!/usr/bin/env python
"""
Script para verificar qué modelos tienen campos de imagen.
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')

import django
django.setup()

from django.apps import apps
from django.db import models

print("=" * 60)
print("MODELOS CON CAMPOS DE IMAGEN")
print("=" * 60)

# Buscar todos los modelos con ImageField o FileField
for model in apps.get_models():
    image_fields = []
    file_fields = []

    for field in model._meta.fields:
        if isinstance(field, models.ImageField):
            image_fields.append(field.name)
        elif isinstance(field, models.FileField):
            file_fields.append(field.name)

    if image_fields or file_fields:
        print(f"\n📦 {model.__name__} (app: {model._meta.app_label})")
        if image_fields:
            print(f"   ImageFields: {', '.join(image_fields)}")
        if file_fields:
            print(f"   FileFields: {', '.join(file_fields)}")

        # Contar objetos con imágenes
        if image_fields:
            total = model.objects.count()
            with_images = 0
            for field_name in image_fields:
                kwargs = {f"{field_name}__isnull": False}
                with_images = model.objects.exclude(**kwargs).count()
                if with_images > 0:
                    print(f"   Total registros: {total}")
                    print(f"   Con imágenes en '{field_name}': {with_images}")

print("\n" + "=" * 60)