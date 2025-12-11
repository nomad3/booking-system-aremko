# Imágenes de la Página de Empresas

## Estado Actual

Las imágenes de la página `/empresas/` están usando URLs temporales de Unsplash (imágenes públicas de alta calidad).

**URLs actuales (temporales)**:
- Hero background: `https://images.unsplash.com/photo-1517836357463-d25dfeac3438`
- Desayuno Gourmet: `https://images.unsplash.com/photo-1414235077428-338989a2e8c0`
- Tinas Calientes: `https://images.unsplash.com/photo-1544161515-4ab6ce6db874`
- Team Building: `https://images.unsplash.com/photo-1522071820081-009f0129c71c`

---

## Cómo Reemplazar con Imágenes Reales

### Paso 1: Coloca las Imágenes Originales

Coloca las siguientes imágenes en este directorio (`temp_images_empresas/`):

1. **desayuno_empresas_aremko.jpg** - Foto del desayuno gourmet corporativo
2. **4_amigas_en_la_calbuco.PNG** - Foto de experiencia en tinas calientes
3. **charla_empresas_aremko.jpg** - Foto de sala ejecutiva o team building

### Paso 2: Configura Variables de Entorno

Asegúrate de tener configuradas las variables de Cloudinary:

```bash
export CLOUDINARY_CLOUD_NAME="tu_cloud_name"
export CLOUDINARY_API_KEY="tu_api_key"
export CLOUDINARY_API_SECRET="tu_api_secret"
```

### Paso 3: Ejecuta el Script de Carga

```bash
cd /Users/jorgeaguilera/Documents/GitHub/booking-system-aremko
python scripts/upload_empresas_images_to_cloudinary.py
```

Este script:
- ✅ Subirá las imágenes a Cloudinary en la carpeta `categorias/`
- ✅ Mostrará las URLs generadas
- ✅ Las imágenes estarán disponibles públicamente via CDN

### Paso 4: Actualiza el Template (Manual)

Una vez subidas las imágenes a Cloudinary, actualiza las URLs en `ventas/templates/ventas/empresas.html`:

**Ejemplo:**
```html
<!-- ANTES (temporal Unsplash) -->
<img src="https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800&q=80" alt="...">

<!-- DESPUÉS (Cloudinary) -->
<img src="https://res.cloudinary.com/TU_CLOUD_NAME/image/upload/v1234567890/categorias/desayuno_empresas_aremko.jpg" alt="...">
```

---

## Imágenes Necesarias

### 1. desayuno_empresas_aremko.jpg
**Usado en:**
- Hero section background (línea 53)
- Card "Experiencia Ejecutiva Completa" (línea 833)
- Galería "Desayuno Gourmet" (línea 991)

**Descripción**: Foto profesional del desayuno gourmet para empresas

---

### 2. 4_amigas_en_la_calbuco.PNG
**Usado en:**
- Card "Desayuno & Wellness" (línea 859)
- Galería "Tinas Calientes" (línea 999)

**Descripción**: Foto de personas disfrutando las tinas calientes con vista al río

---

### 3. charla_empresas_aremko.jpg
**Usado en:**
- Card "Wellness Corporativo" (línea 884)
- Galería "Sala Ejecutiva" (línea 1007)

**Descripción**: Foto de equipo empresarial en actividad de team building o sala ejecutiva

---

## Alternativa: Búsqueda de Imágenes Anteriores

Si ya tenías estas imágenes subidas previamente pero perdiste acceso a Google Cloud Storage, puedes:

1. Buscar en backups locales de tu computadora
2. Revisar email o comunicaciones donde hayas compartido las imágenes
3. Contactar a quien tomó las fotos originales
4. Tomar nuevas fotos profesionales de tus instalaciones

---

## Verificación

Una vez actualizado el template, verifica que las imágenes se vean correctamente en:
- `https://www.aremko.cl/empresas/`

Revisa especialmente:
- ✅ Hero background se ve correctamente
- ✅ Las 3 cards de servicios tienen imágenes
- ✅ La galería muestra las 3 imágenes

---

## Soporte

Si tienes problemas:
1. Verifica que Cloudinary esté configurado: `echo $CLOUDINARY_CLOUD_NAME`
2. Revisa los logs del script de carga
3. Verifica que las imágenes tengan los nombres exactos mencionados arriba
