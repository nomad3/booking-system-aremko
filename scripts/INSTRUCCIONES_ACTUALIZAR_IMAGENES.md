# CÓMO ACTUALIZAR LAS IMÁGENES DE CATEGORÍAS EN RENDER

## Problema
Las imágenes hero no aparecen en las páginas:
- https://www.aremko.cl/tinas/
- https://www.aremko.cl/masajes/
- https://www.aremko.cl/alojamientos/

## Solución Simple (2 minutos) ⭐

### Paso 1: Acceder al Shell de Render

1. Ve a https://dashboard.render.com
2. Entra a tu servicio web (aremko-booking-system o similar)
3. Click en "Shell" en el menú lateral
4. Espera a que se abra la terminal

### Paso 2: Ejecutar el script

En la terminal de Render, ejecuta este ÚNICO comando:

```bash
python scripts/update_category_images_direct.py
```

### Paso 3: Verificar el resultado

El script mostrará:
- ✅ El estado ANTES de actualizar
- ✅ Las actualizaciones realizadas
- ✅ El estado DESPUÉS de actualizar
- ✅ Las URLs finales de Cloudinary

Si ves URLs como `https://res.cloudinary.com/dtuncr1pi/image/upload/...`, entonces funcionó.

### Paso 4: Probar en el navegador

Abre (en modo incógnito o limpia caché):
- https://www.aremko.cl/tinas/
- https://www.aremko.cl/masajes/
- https://www.aremko.cl/alojamientos/

Deberías ver las imágenes hero de fondo.

---

## ¿Qué pasó?

Las imágenes ya están subidas a Cloudinary:
- ✅ `categorias/tinas_hero.png`
- ✅ `categorias/masajes_hero.jpg`
- ✅ `categorias/alojamientos_hero.jpg`

Pero la base de datos de producción todavía no tiene las referencias a estas imágenes en los registros de `CategoriaServicio`.

El código Python actualiza esos registros para que apunten a las imágenes correctas.

---

## Verificación Técnica

Si quieres verificar que todo está bien configurado, en el shell de Django ejecuta:

```python
from ventas.models import CategoriaServicio

# Ver todas las categorías
for cat in CategoriaServicio.objects.all():
    print(f"{cat.id}. {cat.nombre}: {cat.imagen}")
    if cat.imagen:
        print(f"   URL: {cat.imagen.url}")
```

Deberías ver las URLs de Cloudinary.
