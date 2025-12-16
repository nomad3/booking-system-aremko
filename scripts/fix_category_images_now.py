"""
EJECUTA ESTE CÓDIGO EN EL SHELL DE RENDER PARA ACTUALIZAR LAS IMÁGENES
================================================================

Copia y pega todo el código de abajo en el shell de Render.
"""

from ventas.models import CategoriaServicio

print("\n" + "=" * 70)
print("ACTUALIZANDO IMÁGENES DE CATEGORÍAS")
print("=" * 70)

# Estado actual
print("\n📋 Estado ANTES de actualizar:")
print("-" * 70)
for cat in CategoriaServicio.objects.all():
    print(f"{cat.id}. {cat.nombre}")
    print(f"   imagen actual: '{cat.imagen}'")
    if cat.imagen:
        try:
            print(f"   URL: {cat.imagen.url}")
        except:
            print(f"   ⚠️ ERROR generando URL")
    print()

# Actualizar con las rutas de Cloudinary
print("\n🔄 Actualizando...")
print("-" * 70)

try:
    # Tinas Calientes
    cat1 = CategoriaServicio.objects.get(id=1)
    cat1.imagen = 'categorias/tinas_hero.png'
    cat1.save()
    print(f"✅ {cat1.nombre}")
    print(f"   imagen: {cat1.imagen}")
    try:
        print(f"   URL: {cat1.imagen.url}")
    except Exception as e:
        print(f"   ⚠️ Error URL: {e}")
    print()
except Exception as e:
    print(f"❌ Error actualizando Tinas: {e}\n")

try:
    # Masajes
    cat2 = CategoriaServicio.objects.get(id=2)
    cat2.imagen = 'categorias/masajes_hero.jpg'
    cat2.save()
    print(f"✅ {cat2.nombre}")
    print(f"   imagen: {cat2.imagen}")
    try:
        print(f"   URL: {cat2.imagen.url}")
    except Exception as e:
        print(f"   ⚠️ Error URL: {e}")
    print()
except Exception as e:
    print(f"❌ Error actualizando Masajes: {e}\n")

try:
    # Alojamientos
    cat3 = CategoriaServicio.objects.get(id=3)
    cat3.imagen = 'categorias/alojamientos_hero.jpg'
    cat3.save()
    print(f"✅ {cat3.nombre}")
    print(f"   imagen: {cat3.imagen}")
    try:
        print(f"   URL: {cat3.imagen.url}")
    except Exception as e:
        print(f"   ⚠️ Error URL: {e}")
    print()
except Exception as e:
    print(f"❌ Error actualizando Alojamientos: {e}\n")

# Estado final
print("\n📋 Estado DESPUÉS de actualizar:")
print("-" * 70)
for cat in CategoriaServicio.objects.all():
    print(f"{cat.id}. {cat.nombre}")
    print(f"   imagen: '{cat.imagen}'")
    if cat.imagen:
        try:
            print(f"   URL: {cat.imagen.url}")
        except:
            print(f"   ⚠️ ERROR generando URL")
    print()

print("=" * 70)
print("✅ ACTUALIZACIÓN COMPLETADA")
print("=" * 70)
print("\nAhora verifica estos URLs en tu navegador:")
print("  • https://www.aremko.cl/tinas/")
print("  • https://www.aremko.cl/masajes/")
print("  • https://www.aremko.cl/alojamientos/")
print("\n" + "=" * 70)
