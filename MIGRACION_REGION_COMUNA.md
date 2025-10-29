# Migración de Ciudad a Región + Comuna (FASE 4)

Este documento describe el proceso completo de migración de clientes desde el campo `ciudad` (texto libre) a los nuevos campos estructurados `region` y `comuna`.

## 📋 Resumen

- **Objetivo:** Migrar clientes de ciudad texto libre → región + comuna estructuradas
- **Impacto:** ~2,253 clientes con ciudad definida
- **Tiempo estimado:** 5-10 minutos
- **Downtime:** No requiere downtime (campos opcionales)

---

## 🎯 Prerequisitos

✅ Código desplegado en producción (commit `499b69a` o posterior)
✅ Acceso a Render Shell
✅ Backup de base de datos (recomendado)

---

## 📝 Proceso de Migración

### **PASO 1: Acceder a Render Shell**

1. Ir a [Render Dashboard](https://dashboard.render.com/)
2. Seleccionar el servicio Web (backend)
3. Click en "Shell" en el menú lateral
4. Esperar a que cargue el shell

---

### **PASO 2: Crear las Migraciones de Django**

En Render Shell, ejecuta:

```bash
python manage.py makemigrations ventas
```

**Output esperado:**
```
Migrations for 'ventas':
  ventas/migrations/00XX_region_comuna.py
    - Create model Region
    - Create model Comuna
    - Add field region to cliente
    - Add field comuna to cliente
```

---

### **PASO 3: Aplicar las Migraciones**

```bash
python manage.py migrate ventas
```

**Output esperado:**
```
Running migrations:
  Applying ventas.00XX_region_comuna... OK
```

**Esto crea:**
- Tabla `ventas_region` (16 regiones)
- Tabla `ventas_comuna` (346 comunas)
- Columnas `region_id` y `comuna_id` en `ventas_cliente` (NULL por defecto)

---

### **PASO 4: Cargar Fixtures de Regiones y Comunas**

```bash
python manage.py loaddata regiones_comunas_chile
```

**Output esperado:**
```
Installed 58 object(s) from 1 fixture(s)
```

**Esto inserta:**
- 16 regiones oficiales de Chile
- 42 comunas principales (basadas en datos reales)

**Verificar:**
```bash
python manage.py shell
>>> from ventas.models import Region, Comuna
>>> Region.objects.count()
16
>>> Comuna.objects.count()
42
>>> exit()
```

---

### **PASO 5: Ejecutar Migración de Datos**

```bash
python manage.py shell < scripts/migrar_clientes_a_region_comuna.py
```

**Este script:**
1. Verifica que regiones y comunas estén cargadas
2. Analiza todos los clientes con ciudad
3. Mapea ciudad normalizada → (región, comuna)
4. Actualiza clientes usando `.update()` (evita validaciones)
5. Genera reporte detallado

**Output esperado:**
```
====================================================================================================
MIGRACIÓN DE CLIENTES: CIUDAD → REGIÓN + COMUNA
====================================================================================================

📋 VERIFICANDO PREREQUISITOS...
✓ Regiones cargadas:  16
✓ Comunas cargadas:   42

📊 ANÁLISIS DE CLIENTES:
Total de clientes:                   3,029
Clientes con ciudad:                 2,253
Clientes sin ciudad:                   776
Clientes ya con región+comuna:          0

🔍 ANALIZANDO MAPEO CIUDAD → REGIÓN + COMUNA...
✓ Análisis completado:
  • Clientes a migrar:               2,247
  • Clientes extranjeros (skip):         6
  • Clientes sin mapeo (skip):           0

====================================================================================================
PREVIEW DE MIGRACIONES
====================================================================================================
#     CLIENTE                        CIUDAD                    → REGIÓN + COMUNA
----------------------------------------------------------------------------------------------------
1     Bio Mar Chile S.A              Puerto Montt              → Los Lagos / Puerto Montt
2     Claudia Vallejos  Larrondo     Puerto Varas              → Los Lagos / Puerto Varas
3     Claudio Almonacid Silva        Puerto Montt              → Los Lagos / Puerto Montt
...

====================================================================================================
RESUMEN DE MIGRACIONES POR REGIÓN
====================================================================================================

📍 Los Lagos (Total: 1,226 clientes)
   • Puerto Montt: 762 clientes
   • Puerto Varas: 563 clientes
   • Osorno: 95 clientes
...

====================================================================================================
🔄 APLICANDO MIGRACIONES
====================================================================================================

Se migrarán 2,247 clientes...

  ✓ 100 / 2,247 clientes migrados...
  ✓ 200 / 2,247 clientes migrados...
  ...
  ✓ 2,200 / 2,247 clientes migrados...

✅ ¡MIGRACIÓN COMPLETADA EXITOSAMENTE!
====================================================================================================
   • Clientes migrados:              2,247
   • Regiones únicas:                12
   • Tiempo de ejecución:            ~5 segundos

RESUMEN:
   • Clientes con región+comuna:     2,247
   • Clientes extranjeros (sin cambio):  6
   • Clientes sin mapeo (sin cambio):    0

====================================================================================================
```

---

## ✅ Verificación Post-Migración

### **1. Verificar conteos en Django Shell:**

```bash
python manage.py shell
```

```python
from ventas.models import Cliente, Region, Comuna

# Total de clientes migrados
Cliente.objects.filter(region__isnull=False, comuna__isnull=False).count()
# Esperado: ~2,247

# Clientes por región Los Lagos
Cliente.objects.filter(region__codigo='X').count()
# Esperado: ~1,226

# Clientes en Puerto Montt
Cliente.objects.filter(comuna__nombre='Puerto Montt').count()
# Esperado: ~762

# Clientes en Puerto Varas
Cliente.objects.filter(comuna__nombre='Puerto Varas').count()
# Esperado: ~563

# Listado de regiones con clientes
from django.db.models import Count
Region.objects.annotate(num_clientes=Count('clientes')).filter(num_clientes__gt=0)

exit()
```

### **2. Verificar en el admin de Django:**

1. Ir a `/admin/ventas/region/`
2. Verificar que hay 16 regiones
3. Ir a `/admin/ventas/comuna/`
4. Verificar que hay 42 comunas
5. Ir a `/admin/ventas/cliente/`
6. Verificar que clientes tienen región y comuna asignadas

---

## 🔄 Rollback (si algo sale mal)

**Si la migración falla:**

El script usa transacciones atómicas, por lo que si hay un error:
- Todos los cambios se revierten automáticamente
- La base de datos queda en el estado original
- No se pierde información

**Para revertir manualmente (si necesario):**

```bash
python manage.py shell
```

```python
from ventas.models import Cliente

# Limpiar región y comuna de todos los clientes
Cliente.objects.all().update(region=None, comuna=None)

exit()
```

**Para revertir migraciones de base de datos:**

```bash
# Ver migraciones aplicadas
python manage.py showmigrations ventas

# Revertir última migración
python manage.py migrate ventas 00XX_nombre_migracion_anterior
```

---

## 📊 Impacto en la Aplicación

### **Cambios inmediatos:**
- ✅ Clientes tienen región y comuna estructuradas
- ✅ Campo `ciudad` preservado (no se elimina)
- ✅ Queries por región/comuna ahora funcionan
- ✅ Segmentación mejorada

### **Cambios NO aplicados (FASE 5+):**
- ❌ Formularios aún usan campo texto libre `ciudad`
- ❌ Vistas de reporting aún usan campo `ciudad`
- ❌ No hay dropdowns cascada región → comuna

---

## 🚀 Próximos Pasos (FASE 5)

Después de completar la migración:

1. **Actualizar formularios de checkout:**
   - Reemplazar campo texto `ciudad` por dropdowns
   - Implementar cascada: seleccionar región → mostrar comunas

2. **Actualizar vistas de CRM:**
   - Usar `region` y `comuna` en lugar de `ciudad`
   - Actualizar filtros de segmentación

3. **Actualizar reporting:**
   - Gráficos por región
   - Métricas por comuna

4. **Deprecar campo `ciudad`:**
   - Marcarlo como read-only
   - Eventualmente eliminarlo (después de verificar que no se usa)

---

## 🐛 Troubleshooting

### **Error: "No hay regiones en la base de datos"**
**Solución:** Ejecutar `python manage.py loaddata regiones_comunas_chile`

### **Error: "Comuna 'X' no existe en región 'Y'"**
**Solución:** Verificar que las fixtures se cargaron correctamente

### **Error: "Formato de teléfono inválido"**
**Causa:** El script usa `.update()` que NO ejecuta validaciones
**Solución:** Esto no debería ocurrir, pero si pasa, verificar que usas `.update()` y no `.save()`

### **Clientes sin mapeo**
**Solución:** Agregar mapeo en `ventas/data/mapeo_ciudad_region_comuna.py` y re-ejecutar

---

## 📞 Soporte

Si encuentras problemas durante la migración:
1. Capturar el output completo del error
2. Verificar logs en Render
3. Revisar este documento
4. Contactar equipo de desarrollo

---

**Última actualización:** 2025-10-29
**Versión:** FASE 4
**Autor:** Sistema de normalización de ciudades
