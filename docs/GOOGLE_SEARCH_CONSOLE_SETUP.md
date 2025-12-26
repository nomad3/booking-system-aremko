# Configuración de Google Search Console

## 📋 Instrucciones para enviar sitemap.xml

### Paso 1: Acceder a Google Search Console
1. Ve a https://search.google.com/search-console
2. Inicia sesión con tu cuenta de Google de Aremko
3. Si no has agregado la propiedad, selecciona "Agregar propiedad"

### Paso 2: Verificar la propiedad (si aún no está verificada)
**Opción recomendada: Verificación por archivo HTML**
1. Google te dará un archivo HTML para descargar
2. Sube ese archivo a la raíz de tu sitio
3. Verifica que sea accesible en: `https://www.aremko.cl/google[código].html`
4. Click en "Verificar"

**Alternativa: Verificación por DNS**
1. Agrega un registro TXT en tu DNS (Render o proveedor de dominio)
2. Google te dará el código TXT
3. Espera a que se propague (puede tardar hasta 48 horas)

### Paso 3: Enviar el Sitemap
1. En el menú lateral, ve a **"Sitemaps"**
2. En "Añadir un nuevo sitemap", escribe: `sitemap.xml`
3. Click en **"Enviar"**

**URL completa del sitemap:**
```
https://www.aremko.cl/sitemap.xml
```

### Paso 4: Verificar el Sitemap
Después de enviar, Google tardará algunas horas en procesar el sitemap.

**Puedes validar el sitemap antes de enviarlo:**
1. Ve a: https://www.xml-sitemaps.com/validate-xml-sitemap.html
2. Ingresa: `https://www.aremko.cl/sitemap.xml`
3. Click en "Validate"

O directamente en el navegador:
```
https://www.aremko.cl/sitemap.xml
```

---

## 📊 URLs Incluidas en el Sitemap

### URLs Estáticas (Priority Alta)
- **Homepage** `/` - Priority: 1.0, Changefreq: daily
- **Masajes** `/masajes/` - Priority: 0.9, Changefreq: weekly
- **Tinas** `/tinas/` - Priority: 0.9, Changefreq: weekly
- **Alojamientos** `/alojamientos/` - Priority: 0.9, Changefreq: weekly
- **Productos/GiftCards** `/productos/` - Priority: 0.9, Changefreq: weekly

### URLs Corporativas
- **Empresas** `/empresas/` - Priority: 0.7, Changefreq: monthly

### URLs Dinámicas
- **Categorías de Servicios** `/ventas/categoria/[id]/` - Priority: 0.8, Changefreq: weekly
  - Solo categorías con `activo=True`

---

## ✅ Checklist de Validación

Después de enviar el sitemap, verifica:

- [ ] Sitemap enviado en Google Search Console
- [ ] Estado del sitemap: "Correcto" (puede tardar 24-48h)
- [ ] Todas las URLs descubiertas por Google
- [ ] Sin errores en el informe de cobertura
- [ ] robots.txt apunta correctamente al sitemap

---

## 🔍 Monitoreo Continuo

**Revisa semanalmente:**
1. **Cobertura** - ¿Todas las páginas están indexadas?
2. **Rendimiento** - ¿Cómo apareces en búsquedas?
3. **Mejoras** - ¿Hay problemas de usabilidad móvil?
4. **Velocidad** - Core Web Vitals

---

## 🚨 Problemas Comunes

### "Sitemap no encontrado"
- Verifica que https://www.aremko.cl/sitemap.xml sea accesible
- Revisa que el servidor esté devolviendo Content-Type: application/xml

### "URLs bloqueadas por robots.txt"
- Revisa que robots.txt permite el acceso:
  ```
  User-agent: Googlebot
  Allow: /
  ```

### "Sitemap con errores"
- Valida el XML en: https://www.xml-sitemaps.com/validate-xml-sitemap.html
- Verifica que todas las URLs sean absolutas (con dominio completo)

---

## 📌 Próximas Tareas SEO

Después de configurar Google Search Console:
- [ ] Configurar Google Analytics 4
- [ ] Implementar lazy loading de imágenes
- [ ] Convertir imágenes a WebP
- [ ] Optimizar velocidad de carga
- [ ] Configurar schema.org markup
- [ ] Crear páginas de blog (para contenido SEO)

---

**Fecha de creación:** 2025-12-26
**Última actualización:** 2025-12-26
