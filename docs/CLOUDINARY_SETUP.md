# ☁️ Configuración de Cloudinary para Aremko

## 📋 ¿Por qué Cloudinary?

Cloudinary ofrece ventajas significativas sobre Google Cloud Storage:

✅ **Gratis hasta 25GB** de almacenamiento
✅ **Transformación automática** de imágenes (resize, crop, optimize)
✅ **CDN global** incluido sin costo extra
✅ **Optimización automática** de formato (WebP, AVIF)
✅ **URLs de transformación** dinámicas
✅ **Configuración simple** en 5 minutos

## 🚀 Guía de Configuración Rápida

### Paso 1: Crear Cuenta en Cloudinary

1. **Registrarse en:** https://cloudinary.com/users/register/free
2. **Completar el formulario:**
   - Email empresarial
   - Nombre de empresa: Aremko
   - Plan: Free
3. **Confirmar email** que recibirás
4. **Acceder al Dashboard**

### Paso 2: Obtener Credenciales

Una vez en el Dashboard de Cloudinary:

1. En la página principal verás un cuadro con tus credenciales:
   ```
   Cloud Name: dxxxxxxxxx
   API Key: 123456789012345
   API Secret: xxxxxxxxxxxxxxxxxxxxxx
   ```

2. **COPIA estos 3 valores** - Los necesitarás en el siguiente paso

### Paso 3: Configurar Variables en Render

1. Ir a https://dashboard.render.com
2. Seleccionar tu servicio web de Django
3. Ir a la sección **"Environment"**
4. Agregar estas variables:

```bash
CLOUDINARY_CLOUD_NAME=dxxxxxxxxx
CLOUDINARY_API_KEY=123456789012345
CLOUDINARY_API_SECRET=xxxxxxxxxxxxxxxxxxxxxx
```

5. Click en **"Save Changes"**
6. El servicio se redesplegará automáticamente

### Paso 4: Verificar la Configuración

Una vez que Render termine de desplegar:

1. Acceder al Shell de Render
2. Ejecutar el script de prueba:

```bash
cd /app
python scripts/test_cloudinary.py
```

Deberías ver:
```
✅ PRUEBA COMPLETADA EXITOSAMENTE
Cloudinary está configurado y funcionando correctamente.
```

### Paso 5: Migrar Imágenes Existentes

Para migrar las imágenes desde Google Cloud Storage:

```bash
python scripts/migrate_to_cloudinary.py
```

El script:
- Descargará cada imagen del storage antiguo
- La subirá a Cloudinary con optimizaciones
- Actualizará las URLs en la base de datos
- Generará versiones thumbnail y móvil

## 🎨 URLs de Transformación

Cloudinary permite transformar imágenes sobre la marcha usando URLs:

### Estructura de URL:
```
https://res.cloudinary.com/{cloud_name}/image/upload/{transformaciones}/{public_id}
```

### Transformaciones Útiles:

#### Thumbnail (200x200)
```
/upload/c_thumb,w_200,h_200,g_center/
```

#### Móvil Optimizado
```
/upload/c_scale,w_500,q_auto,f_auto/
```

#### Gift Card (800x600)
```
/upload/c_fit,w_800,h_600,q_90/
```

#### Auto Optimización
```
/upload/q_auto,f_auto/
```

## 📝 Uso en Django

### Subir una imagen:
```python
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

# Subir imagen
file = ContentFile(imagen_bytes, name='foto.jpg')
path = default_storage.save('productos/foto.jpg', file)
url = default_storage.url(path)
```

### En los modelos:
```python
class Servicio(models.Model):
    imagen = models.ImageField(
        upload_to='servicios/',
        blank=True,
        null=True
    )
```

### En las templates:
```html
<!-- Imagen original -->
<img src="{{ servicio.imagen.url }}" alt="Servicio">

<!-- Thumbnail -->
<img src="{{ servicio.imagen.url|cloudinary_transform:'c_thumb,w_200,h_200' }}" alt="Thumbnail">
```

## 🔧 Configuración Avanzada

### Transformaciones Predefinidas

En `settings.py` puedes definir transformaciones nombradas:

```python
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': 'tu_cloud_name',
    'API_KEY': 'tu_api_key',
    'API_SECRET': 'tu_api_secret',
    'SECURE': True,
    'MEDIA_TAG': 'media',

    # Transformaciones predefinidas
    'TRANSFORMATIONS': {
        'thumbnail': {
            'width': 200,
            'height': 200,
            'crop': 'thumb',
            'gravity': 'center'
        },
        'mobile': {
            'width': 500,
            'crop': 'scale',
            'quality': 'auto',
            'fetch_format': 'auto'
        },
        'giftcard': {
            'width': 800,
            'height': 600,
            'crop': 'fit',
            'quality': 90
        }
    }
}
```

### Optimización Automática

Cloudinary puede optimizar automáticamente todas las imágenes:

- **q_auto**: Ajusta la calidad según el contenido
- **f_auto**: Selecciona el mejor formato (WebP, AVIF, etc.)
- **dpr_auto**: Ajusta para pantallas Retina
- **w_auto**: Ajusta el ancho según el viewport

## 📊 Dashboard de Cloudinary

### Métricas Importantes:

1. **Media Library**: Ver todas las imágenes subidas
2. **Transformations**: Ver qué transformaciones se usan más
3. **Analytics**: Bandwidth y requests
4. **Settings**: Configurar opciones de optimización

### Límites del Plan Gratis:

- **25 GB** de almacenamiento total
- **25 GB** de bandwidth mensual
- **25,000** transformaciones mensuales
- **Ilimitadas** subidas

## 🚨 Troubleshooting

### Error: "Invalid credentials"
- Verificar que las 3 variables de entorno están configuradas
- Verificar que no hay espacios extras en los valores

### Error: "Upload preset not found"
- El script usa upload directo, no presets
- Verificar que el API Secret es correcto

### Las imágenes no se optimizan
- Agregar `q_auto,f_auto` a las URLs
- Verificar en el dashboard que las transformaciones están activas

### Error 500 al subir imágenes
- Verificar que `django-cloudinary-storage` está instalado
- Verificar que las apps están en el orden correcto en INSTALLED_APPS

## 🔐 Seguridad

### Mejores Prácticas:

1. **Nunca exponer el API Secret** en código o logs
2. **Usar HTTPS siempre** (configurado por defecto)
3. **Configurar restricciones** en el dashboard si es necesario
4. **Monitorear uso** para evitar exceder límites

### Backup:

Cloudinary mantiene backups automáticos, pero es recomendable:
- Mantener copias locales de imágenes críticas
- Exportar URLs periódicamente
- Documentar las transformaciones usadas

## 📚 Recursos

- [Documentación Oficial](https://cloudinary.com/documentation)
- [Django Integration](https://cloudinary.com/documentation/django_integration)
- [Transformation Reference](https://cloudinary.com/documentation/transformation_reference)
- [Dashboard](https://console.cloudinary.com)

## ✅ Checklist de Verificación

- [ ] Cuenta creada en Cloudinary
- [ ] Credenciales obtenidas del dashboard
- [ ] Variables configuradas en Render
- [ ] Script de prueba ejecutado exitosamente
- [ ] Imágenes migradas desde GCS
- [ ] Django Admin permite subir imágenes
- [ ] Gift Cards muestran imágenes correctamente
- [ ] Sitio web carga imágenes rápidamente

---

**Última actualización**: 2025-12-09
**Soporte**: Si tienes problemas, revisa el dashboard de Cloudinary o los logs de Render.