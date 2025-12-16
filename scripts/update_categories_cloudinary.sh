#!/bin/bash

echo "================================================================================"
echo "ACTUALIZAR CATEGORÍAS CON IMÁGENES DE CLOUDINARY"
echo "================================================================================"
echo ""
echo "Ejecuta estos comandos en el shell de Render:"
echo ""
echo "---"
echo ""
cat << 'PYTHON_CODE'
from ventas.models import CategoriaServicio

# Verificar estado actual
print("\n📋 Estado actual de las categorías:")
print("=" * 60)
for cat in CategoriaServicio.objects.all():
    print(f"{cat.id}. {cat.nombre}")
    print(f"   Imagen actual: {cat.imagen}")
    if cat.imagen:
        try:
            print(f"   URL: {cat.imagen.url}")
        except:
            print(f"   ⚠️ No se puede generar URL")
    print()

# Actualizar con las rutas correctas de Cloudinary
print("\n🔄 Actualizando categorías...")
print("=" * 60)

# Tinas Calientes
cat1 = CategoriaServicio.objects.get(id=1)
cat1.imagen = 'categorias/tinas_hero.png'
cat1.save()
print(f"✅ {cat1.nombre}: {cat1.imagen}")
try:
    print(f"   URL: {cat1.imagen.url}")
except Exception as e:
    print(f"   ⚠️ Error generando URL: {e}")

# Masajes
cat2 = CategoriaServicio.objects.get(id=2)
cat2.imagen = 'categorias/masajes_hero.jpg'
cat2.save()
print(f"✅ {cat2.nombre}: {cat2.imagen}")
try:
    print(f"   URL: {cat2.imagen.url}")
except Exception as e:
    print(f"   ⚠️ Error generando URL: {e}")

# Alojamientos
cat3 = CategoriaServicio.objects.get(id=3)
cat3.imagen = 'categorias/alojamientos_hero.jpg'
cat3.save()
print(f"✅ {cat3.nombre}: {cat3.imagen}")
try:
    print(f"   URL: {cat3.imagen.url}")
except Exception as e:
    print(f"   ⚠️ Error generando URL: {e}")

print("\n" + "=" * 60)
print("✅ Actualización completada")
print("\nVerifica las páginas:")
print("  - https://www.aremko.cl/tinas/")
print("  - https://www.aremko.cl/masajes/")
print("  - https://www.aremko.cl/alojamientos/")

PYTHON_CODE

echo ""
echo "---"
echo ""
echo "Copia y pega el código Python de arriba en el shell de Render"
echo "================================================================================"
