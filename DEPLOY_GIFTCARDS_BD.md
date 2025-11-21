# 🚀 Despliegue: Migración de GiftCards a Base de Datos

## 📋 Resumen de Cambios

Se implementó **Opción B**: Migrar las 16 experiencias GiftCard desde código hardcodeado a la base de datos, permitiendo:

✅ Editar precios sin tocar código
✅ Subir/cambiar imágenes desde el admin
✅ Activar/desactivar experiencias
✅ Reordenar experiencias
✅ Base lista para futura implementación de cupones de descuento

---

## 📦 Archivos Creados/Modificados

### **Nuevos Archivos**

1. **`ventas/migrations/0061_giftcardexperiencia.py`**
   - Migración que crea la tabla `GiftCardExperiencia`

2. **`poblar_experiencias_giftcard.py`**
   - Script para poblar las 16 experiencias en la BD

3. **`DEPLOY_GIFTCARDS_BD.md`** (este archivo)
   - Instrucciones de despliegue

### **Archivos Modificados**

1. **`ventas/models.py`**
   - Agregado modelo `GiftCardExperiencia` (líneas 2609-2721)

2. **`ventas/views/giftcard_views.py`**
   - Importado `GiftCardExperiencia` (línea 17)
   - Reemplazado array hardcodeado con consulta a BD (líneas 390-408)

3. **`ventas/admin.py`**
   - Agregado admin para `GiftCardExperiencia` (líneas 867-955)

---

## 🔧 Pasos de Despliegue en Render

### **Paso 1: Push a GitHub**

```bash
git add .
git commit -m "Migrar GiftCards a base de datos

- Crear modelo GiftCardExperiencia con ImageField
- Migración 0061 para crear tabla
- Script poblar_experiencias_giftcard.py
- Admin interface para gestionar experiencias
- Actualizar giftcard_wizard para leer de BD

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
git push
```

### **Paso 2: Ejecutar Migración en Render Shell**

1. Ir a dashboard de Render → Tu servicio
2. Abrir **Shell** (botón arriba a la derecha)
3. Ejecutar:

```bash
python manage.py migrate ventas
```

**Output esperado:**
```
Running migrations:
  Applying ventas.0061_giftcardexperiencia... OK
```

### **Paso 3: Poblar las 16 Experiencias**

En la misma shell de Render, ejecutar:

```bash
python poblar_experiencias_giftcard.py
```

**Output esperado:**
```
🎁 Iniciando población de experiencias Gift Card...

✅ Creada: Tina para 2 ($50,000)
✅ Creada: Tina + Masajes (Dom-Jue) ($95,000)
✅ Creada: Tina + Masajes (Vie-Sáb) ($130,000)
✅ Creada: Pack 4 Personas ($190,000)
✅ Creada: Pack 6 Personas ($285,000)
✅ Creada: Masaje Piedras Calientes ($45,000)
✅ Creada: Masaje Deportivo ($45,000)
✅ Creada: Drenaje Linfático ($45,000)
✅ Creada: Masaje para Dos ($80,000)
✅ Creada: Alojamiento + Tinas (Dom-Jue) ($95,000)
✅ Creada: Alojamiento + Tinas (Vie-Sáb) ($140,000)
✅ Creada: Paquete Romántico Completo ($150,000)
✅ Creada: Tina + Ambientación Cumpleaños ($88,000)
✅ Creada: Tina + Celebración Especial ($82,000)
✅ Creada: Monto Libre (Valor variable)

============================================================
📊 Resumen:
   • Experiencias creadas: 15
   • Experiencias actualizadas: 0
   • Errores: 0
   • Total en BD: 15
============================================================

📋 Experiencias por categoría:
   • Tinas y Hidromasajes: 5 experiencias
   • Masajes: 4 experiencias
   • Packs Spa: 5 experiencias
   • Tarjetas de Valor: 1 experiencias

✨ ¡Listo! Las experiencias están en la base de datos.
⚠️  NOTA: Recuerda que las imágenes deben existir en static/images/
    Si no existen, súbelas o actualiza las rutas desde el admin.
```

---

## ⚠️ IMPORTANTE: Sobre las Imágenes

### **Situación Actual**

Las experiencias usan rutas de imágenes que **ya existían** en el código hardcodeado:

```
images/tinas.jpg
images/tinas_masajes.jpg
images/masaje_piedras.jpg
images/masaje_deportivo.jpg
images/drenaje_linfatico.jpg
images/masaje_pareja.jpg
images/alojamiento_tinas.jpg
images/alojamiento_romantico.jpg
images/tina_cumpleanos.jpg
images/tina_celebracion.jpg
images/gift_generic.jpg
```

### **Opciones de Manejo**

**Opción A: Mantener las rutas actuales (RECOMENDADO para primera fase)**
- Si las imágenes ya existen en `static/images/` o `staticfiles/images/`
- NO requiere cambios inmediatos
- Funciona igual que antes

**Opción B: Migrar a ImageField con subida de archivos**
- Ir al admin de Django
- Editar cada experiencia
- Subir nuevas imágenes → se guardarán en `media/giftcards/experiencias/`
- Las nuevas imágenes se servirán desde el directorio `media/`

### **Verificar Imágenes en Producción**

```bash
# En shell de Render
ls -la staticfiles/images/ | grep -E "tinas|masaje|alojamiento|gift_generic"
```

Si faltan imágenes, puedes:
1. Subirlas manualmente vía SFTP/SCP a `staticfiles/images/`
2. O usar el admin para subir nuevas imágenes

---

## 🧪 Verificación Post-Despliegue

### **1. Verificar que el wizard carga**

Ir a: `https://www.aremko.cl/ventas/giftcards/wizard/`

- Debe mostrar las 15 experiencias organizadas por categoría
- Verificar que los precios son correctos
- Verificar que las imágenes se ven

### **2. Verificar el admin**

Ir a: `https://www.aremko.cl/admin/ventas/giftcardexperiencia/`

- Debe mostrar las 15 experiencias
- Filtros por categoría funcionan
- Editar una experiencia y cambiar precio
- Guardar → verificar que el cambio aparece en el wizard

### **3. Probar compra completa**

1. Ir al wizard
2. Seleccionar experiencia "Tina para 2" ($50.000)
3. Completar wizard hasta el final
4. Verificar que la GiftCard se crea correctamente

---

## 🔍 Troubleshooting

### **Error: "No hay experiencias GiftCard activas"**

**Causa:** No se ejecutó el script de población o se marcaron todas como `activo=False`

**Solución:**
```bash
python poblar_experiencias_giftcard.py
```

### **Error: "No module named 'ventas.models.GiftCardExperiencia'"**

**Causa:** No se ejecutó la migración

**Solución:**
```bash
python manage.py migrate ventas
```

### **Imágenes no se ven**

**Causa 1:** Las rutas no existen en `static/images/`

**Solución:**
```bash
# Verificar en shell de Render
ls -la staticfiles/images/
```

**Causa 2:** STATIC_URL mal configurado

**Solución:** Verificar en settings.py:
```python
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
```

### **Admin no muestra el modelo**

**Causa:** No se importó correctamente en admin.py

**Solución:** Verificar que línea 867 de `admin.py` tiene:
```python
@admin.register(models.GiftCardExperiencia)
```

---

## 📈 Próximos Pasos (Fase 2: Cupones)

Una vez que confirmes que las experiencias funcionan correctamente en producción:

1. **Implementar modelo `CuponDescuento`**
2. **Crear API de validación de cupones**
3. **Agregar campo de cupón al wizard**
4. **Crear cupones de ejemplo** (MADRE, VERANO2024, etc.)

Esto está documentado en `PROPUESTA_GIFTCARDS_DB_Y_CUPONES.md`

---

## ✅ Checklist de Despliegue

- [ ] Push a GitHub completado
- [ ] Migración ejecutada en Render (`python manage.py migrate ventas`)
- [ ] Script de población ejecutado (`python poblar_experiencias_giftcard.py`)
- [ ] Wizard carga las 15 experiencias correctamente
- [ ] Admin muestra modelo GiftCardExperiencia
- [ ] Imágenes se visualizan correctamente
- [ ] Prueba de compra completa exitosa
- [ ] Editar precio desde admin funciona

---

## 📞 Si Necesitas Ayuda

Si algo falla durante el despliegue:

1. Captura el error completo de la shell de Render
2. Verifica que todas las migraciones anteriores se aplicaron: `python manage.py showmigrations ventas`
3. Revisa logs de Render para errores de importación
4. Comparte el error conmigo para debuggear

---

🎉 **¡Listo!** Una vez completados estos pasos, podrás editar precios e imágenes de GiftCards desde el admin sin tocar código.
