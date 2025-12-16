# Generated migration to update category hero images with Cloudinary URLs

from django.db import migrations


def update_category_images(apps, schema_editor):
    """
    Actualiza las imágenes de hero de las categorías con las URLs de Cloudinary
    """
    CategoriaServicio = apps.get_model('ventas', 'CategoriaServicio')

    # Mapeo de categorías a sus imágenes en Cloudinary
    # Para django-cloudinary-storage, guardamos la ruta relativa desde MEDIA_ROOT
    updates = [
        {
            'id': 1,
            'nombre': 'Tinas Calientes',
            'imagen': 'categorias/tinas_hero.png'
        },
        {
            'id': 2,
            'nombre': 'Masajes',
            'imagen': 'categorias/masajes_hero.jpg'
        },
        {
            'id': 3,
            'nombre': 'Alojamientos',
            'imagen': 'categorias/alojamientos_hero.jpg'
        },
    ]

    for item in updates:
        try:
            categoria = CategoriaServicio.objects.get(id=item['id'])
            categoria.imagen = item['imagen']
            categoria.save()
            print(f"✅ Actualizada: {item['nombre']} -> {item['imagen']}")
        except CategoriaServicio.DoesNotExist:
            print(f"⚠️  Categoría {item['nombre']} (ID: {item['id']}) no encontrada")


def reverse_update(apps, schema_editor):
    """
    Revertir los cambios (dejar las imágenes vacías)
    """
    CategoriaServicio = apps.get_model('ventas', 'CategoriaServicio')

    for cat_id in [1, 2, 3]:
        try:
            categoria = CategoriaServicio.objects.get(id=cat_id)
            categoria.imagen = ''
            categoria.save()
        except CategoriaServicio.DoesNotExist:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0066_add_web_fields_to_producto'),
    ]

    operations = [
        migrations.RunPython(update_category_images, reverse_update),
    ]
