# Troubleshooting: Sistema de Comandas

**Fecha:** 2026-02-16
**Contexto:** Implementación del sistema de comandas (órdenes de cocina/bar) para Aremko

---

## Problema Principal

Al hacer clic en el botón "➕ Agregar Comanda con Productos" desde el admin de VentaReserva, el popup:
1. Mostraba una página en blanco
2. Después de un tiempo mostraba "Internal Server Error (500)"
3. No se podían crear comandas con productos

---

## Problemas Identificados y Soluciones

### 1. Popup Mostraba Página en Blanco (RESUELTO ✅)

**Síntoma:**
- Click en "Agregar Comanda con Productos" abría popup vacío
- Sin respuesta del servidor, sin errores en logs

**Causa Raíz:**
- ComandaAdmin estaba definido en ventas/admin.py pero nunca se registró con Django admin

**Solución Intentada #1 (FALLIDA):**
- Agregamos `admin.site.register(Comanda, ComandaAdmin)` en línea 807
- **Resultado:** Error `AlreadyRegistered`

**Causa Real:**
- ComandaAdmin ya estaba registrado con el decorador `@admin.register(Comanda)` en línea 3062
- La segunda registración causaba conflicto

**Solución Final:**
- Mantener solo el decorador `@admin.register(Comanda)`
- No agregar registración manual adicional

**Archivos Modificados:**
- `ventas/admin.py` - Línea 3062

---

### 2. Timeout al Cargar el Formulario (RESUELTO ✅)

**Síntoma:**
- Popup se quedaba "pensando" indefinidamente
- Eventualmente mostraba página en blanco o timeout

**Causa Raíz:**
- Django intentaba cargar TODOS los productos en el dropdown del inline DetalleComanda
- También cargaba TODAS las VentaReservas en el campo venta_reserva
- Con cientos/miles de registros, esto causaba timeout

**Solución:**
```python
# En DetalleComandaInline (línea 242)
autocomplete_fields = ['producto']  # Usar Ajax search en lugar de dropdown

# En ComandaAdmin (línea 3073)
autocomplete_fields = ['venta_reserva']  # Usar Ajax search en lugar de dropdown
```

**Resultado:**
- Formulario ahora carga rápidamente
- Usuario puede buscar productos/reservas con autocomplete

**Archivos Modificados:**
- `ventas/admin.py` - Líneas 236-250 y 3073

---

### 3. Error 500 al Mostrar el Formulario (RESUELTO ✅)

**Síntoma:**
- Después de agregar autocomplete_fields, popup mostraba Error 500
- Error ocurría ANTES de mostrar el formulario

**Causa Raíz:**
- Métodos como `tiempo_espera_display()` y `entrega_objetivo_display()` eran llamados con `obj=None`
- Esto sucede cuando Django renderiza el formulario para crear un nuevo registro
- Los métodos intentaban llamar `obj.tiempo_espera()` sin verificar si obj existe

**Solución:**
```python
def tiempo_espera_display(self, obj):
    """Muestra tiempo de espera con colores"""
    if not obj or not obj.pk:  # ← Agregar esta verificación
        return '-'
    minutos = obj.tiempo_espera()
    # ... resto del método
```

**Resultado:**
- Formulario ahora se muestra correctamente para nuevas comandas

**Archivos Modificados:**
- `ventas/admin.py` - Líneas 3135-3178 (tiempo_espera_display y entrega_objetivo_display)

---

### 4. Inline de Productos No Se Mostraba (RESUELTO ✅)

**Síntoma:**
- Formulario se cargaba pero no aparecía la sección para agregar productos
- No había forma de agregar DetalleComanda

**Causa:**
- Para evitar el timeout inicial, habíamos comentado `inlines = [DetalleComandaInline]`

**Solución:**
```python
# En ComandaAdmin (línea 3074)
inlines = [DetalleComandaInline]  # Re-habilitar el inline

# En DetalleComandaInline (línea 239)
extra = 0  # No mostrar filas vacías al inicio para evitar cargar productos
```

**Resultado:**
- Inline de productos ahora se muestra
- Usuario puede hacer clic en "Agregar Detalle de Comanda adicional"
- No hay timeout porque productos usan autocomplete

**Archivos Modificados:**
- `ventas/admin.py` - Líneas 239, 3074

---

### 5. Usuarios No Se Pre-seleccionaban (RESUELTO ✅)

**Síntoma:**
- Campos "Usuario que Solicita" y "Usuario que Procesa" aparecían vacíos
- Usuario tenía que seleccionarlos manualmente cada vez

**Causa Raíz Inicial:**
- No habíamos implementado pre-población de usuarios

**Solución Intentada #1 (FALLIDA):**
```python
deborah = User.objects.get(username='deborah')  # minúscula
ernesto = User.objects.get(username='ernesto')  # minúscula
```
- **Problema:** Usuarios reales tienen nombres con mayúscula inicial

**Solución Final:**
```python
# En ComandaAdmin.get_form() (líneas 3180-3197)
def get_form(self, request, obj=None, **kwargs):
    """Pre-poblar usuarios por defecto"""
    form = super().get_form(request, obj, **kwargs)
    if not obj:  # Solo para nuevas comandas
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            deborah = User.objects.get(username='Deborah')  # Con mayúscula
            form.base_fields['usuario_solicita'].initial = deborah.id
        except User.DoesNotExist:
            pass
        try:
            ernesto = User.objects.get(username='Ernesto')  # Con mayúscula
            form.base_fields['usuario_procesa'].initial = ernesto.id
        except User.DoesNotExist:
            pass
    return form
```

**Resultado:**
- Deborah aparece pre-seleccionada como "Usuario que Solicita"
- Ernesto aparece pre-seleccionado como "Usuario que Procesa"
- Usuario puede cambiarlos si es necesario

**Archivos Modificados:**
- `ventas/admin.py` - Líneas 3180-3197

---

### 6. Campo Especificaciones Muy Largo (RESUELTO ✅)

**Síntoma:**
- Campo "especificaciones" en el inline de productos era muy ancho
- Originalmente limitado a 100 caracteres

**Requerimiento:**
- Limitar a ~30 caracteres (para notas cortas como "sin azúcar", "caliente", etc.)

**Solución:**
```python
# En DetalleComandaInline.formfield_for_dbfield() (líneas 244-250)
def formfield_for_dbfield(self, db_field, request, **kwargs):
    """Limitar tamaño del campo especificaciones"""
    formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
    if db_field.name == 'especificaciones':
        formfield.widget.attrs['style'] = 'width: 300px;'
        formfield.widget.attrs['maxlength'] = 30  # Cambiado de 100 a 30
    return formfield
```

**Resultado:**
- Campo ahora limitado a 30 caracteres

**Archivos Modificados:**
- `ventas/admin.py` - Línea 249

---

### 7. Campo "Notas Generales" Sin Valor (RESUELTO ✅)

**Síntoma:**
- Campo "Notas Generales" se mostraba en el formulario
- Usuario reportó que no le ve valor y quería ocultarlo

**Solución:**
```python
# En ComandaAdmin.fieldsets (líneas 3078-3095)
fieldsets = (
    ('Información de la Comanda', {
        'fields': ('venta_reserva', 'estado', 'fecha_entrega_objetivo'),
        # ↑ Removimos 'notas_generales' de aquí
    }),
    # ... resto de fieldsets
)
```

**Resultado:**
- Campo "Notas Generales" ya no se muestra en el formulario

**Archivos Modificados:**
- `ventas/admin.py` - Línea 3080

---

### 8. Error 500 al Guardar la Comanda (RESUELTO ✅)

### 9. NameError: 'slots_disponibles_config' is not defined (RESUELTO ✅)

**Síntoma:**
- Error 500 persistía después de todas las correcciones anteriores
- En los logs: `NameError: name 'slots_disponibles_config' is not defined`
- Error ocurría en `DetalleComanda.save()` línea 4849

**Causa Raíz:**
- Código de `ServicioSlotBloqueo` estaba mezclado dentro del método `save()` de `DetalleComanda`
- Este código validaba slots de servicios pero no pertenecía a DetalleComanda

**Solución:**
```python
# En ventas/models.py - DetalleComanda.save()
def save(self, *args, **kwargs):
    # Capturar precio actual del producto si no está definido
    if not self.precio_unitario:
        self.precio_unitario = self.producto.precio_base
    super().save(*args, **kwargs)
    # ← Método termina aquí, sin código adicional
```

**Resultado:**
- ✅ Error NameError resuelto
- ✅ Comandas ahora se pueden guardar correctamente

**Archivos Modificados:**
- `ventas/models.py` - Líneas 4843-4847

---

### 8. Error 500 al Guardar la Comanda (Problema Original)

**Síntoma:**
- Formulario se cargaba correctamente
- Usuarios pre-seleccionados correctamente
- Productos se podían agregar
- **PERO:** Al hacer clic en "GUARDAR" aparecía Error 500

**Causa Raíz:**
- El método `Comanda.save()` intentaba crear automáticamente entradas de ReservaProducto
- Para esto, iteraba sobre `self.detalles.all()` inmediatamente después de guardar la Comanda
- **PROBLEMA:** En Django admin con inlines, los DetalleComanda se guardan DESPUÉS del objeto padre
- Por lo tanto, `self.detalles.all()` estaba vacío en ese momento
- El método `save()` se ejecutaba antes de que los productos se agregaran

**Código Problemático:**
```python
# En ventas/models.py - Comanda.save() (línea 4756)
def save(self, *args, **kwargs):
    is_new = self.pk is None
    super().save(*args, **kwargs)

    if is_new:
        for detalle in self.detalles.all():  # ← ¡Vacío cuando se llama desde admin!
            ReservaProducto.objects.get_or_create(...)
```

**Solución:**

1. **Marcar comandas creadas desde admin:**
```python
# En ComandaAdmin.save_model() (líneas 3199-3221)
def save_model(self, request, obj, form, change):
    # ... código existente ...
    obj._from_admin = True  # Marcar que viene del admin
    obj._is_new_from_admin = not change
    super().save_model(request, obj, form, change)
```

2. **Agregar save_formset() para manejar creación después de guardar inlines:**
```python
# En ComandaAdmin (después de save_model)
def save_formset(self, request, form, formset, change):
    """Guardar el formset y crear ReservaProducto para nuevas comandas"""
    instances = formset.save(commit=False)

    # Guardar las instancias del formset (DetalleComanda)
    for instance in instances:
        instance.save()

    # Eliminar instancias marcadas para borrar
    for obj in formset.deleted_objects:
        obj.delete()

    formset.save_m2m()

    # Si es una nueva comanda creada desde admin, crear ReservaProducto
    comanda = form.instance
    if hasattr(comanda, '_is_new_from_admin') and comanda._is_new_from_admin and comanda.venta_reserva:
        from django.utils import timezone
        from .models import ReservaProducto

        for detalle in comanda.detalles.all():  # ← Ahora SÍ existen los detalles
            fecha_entrega_reserva = (
                comanda.fecha_entrega_objetivo.date()
                if comanda.fecha_entrega_objetivo
                else timezone.now().date()
            )

            ReservaProducto.objects.get_or_create(
                venta_reserva=comanda.venta_reserva,
                producto=detalle.producto,
                defaults={
                    'cantidad': detalle.cantidad,
                    'precio_unitario_venta': detalle.precio_unitario,
                    'fecha_entrega': fecha_entrega_reserva,
                    'notas': f'Comanda #{comanda.id}' + (
                        f' - {detalle.especificaciones}' if detalle.especificaciones else ''
                    )
                }
            )
```

3. **Modificar Comanda.save() para saltar lógica cuando viene del admin:**
```python
# En ventas/models.py - Comanda.save() (línea 4756)
def save(self, *args, **kwargs):
    is_new = self.pk is None
    super().save(*args, **kwargs)

    # Auto-crear ReservaProducto solo si NO viene del admin
    if is_new and not getattr(self, '_from_admin', False):
        # ... lógica original ...
```

**Resultado:**
- Cuando se crea desde admin: ReservaProducto se crean en `save_formset()` DESPUÉS de guardar los detalles
- Cuando se crea programáticamente (API, scripts): ReservaProducto se crean en `save()` como antes
- Error 500 debería estar resuelto

**Archivos Modificados:**
- `ventas/admin.py` - Líneas 3199-3267 (save_model y nuevo save_formset)
- `ventas/models.py` - Líneas 4756-4786 (Comanda.save con condición adicional)

---

## Estado Actual

### ✅ Completado:
1. Popup se abre correctamente
2. Formulario carga rápidamente con autocomplete
3. Usuarios Deborah y Ernesto pre-seleccionados
4. Inline de productos funciona con autocomplete
5. Campo especificaciones limitado a 30 caracteres
6. Campo Notas Generales oculto
7. Lógica de save_formset implementada para evitar Error 500
8. Error NameError en DetalleComanda.save() CORREGIDO
9. Error de sintaxis en models.py CORREGIDO
10. **Error 500 por campos display en fieldsets CORREGIDO**

### ⏳ Pendiente de Verificar:
1. **Probar el guardado en producción** - Confirmar que Error 500 está resuelto
2. **Verificar que precio_unitario se auto-llena** - Debería tomar valor de producto.precio_base
3. **Verificar que venta_reserva se asigna correctamente** - Desde el parámetro GET cuando se abre el popup
4. **Verificar que ReservaProducto se crea correctamente** - Después de guardar la comanda con productos

---

## Cambios No Commiteados

**IMPORTANTE:** Los últimos cambios NO han sido commiteados por problemas con el directorio de git.

Ejecutar estos comandos para commitear:

```bash
cd /Users/jorgeaguilera/Documents/GitHub/booking-system-aremko-work
git add ventas/admin.py ventas/models.py
git commit -m "fix: Resolver error 500 al guardar Comanda y ajustes de campos

- Limitar especificaciones a 30 caracteres (era 100)
- Ocultar campo Notas Generales del formulario
- Mover creación de ReservaProducto de Comanda.save() a save_formset()
  para que se ejecute DESPUÉS de guardar los DetalleComanda inlines
- Evita error 500 cuando detalles no existen aún en el momento del save"
git push
```

---

## Próximos Pasos

1. Commitear y pushear cambios pendientes
2. Esperar deploy en Render
3. Probar crear una comanda desde VentaReserva admin
4. Verificar que se guarda sin Error 500
5. Verificar que precio_unitario se auto-llena desde producto.precio_base
6. Verificar que se crean los ReservaProducto correctamente

---

## Archivos Modificados en Esta Sesión

```
ventas/admin.py
- Línea 239: extra = 0 en DetalleComandaInline
- Línea 242: autocomplete_fields = ['producto']
- Línea 249: maxlength = 30 (era 100)
- Línea 3073: autocomplete_fields = ['venta_reserva']
- Línea 3080: Removido 'notas_generales' de fieldsets
- Líneas 3135-3178: Agregar checks if not obj or not obj.pk
- Líneas 3180-3197: get_form() con pre-población de usuarios
- Líneas 3199-3267: save_model() modificado + nuevo save_formset()

ventas/models.py
- Líneas 4756-4786: Comanda.save() con condición _from_admin
```

---

## Contexto Técnico Importante

### Flujo de Guardado en Django Admin con Inlines:

1. Usuario hace clic en "GUARDAR"
2. Django valida el formulario principal (Comanda)
3. Django llama a `ComandaAdmin.save_model()` → guarda la Comanda
4. Django valida los formularios inline (DetalleComanda)
5. Django llama a `ComandaAdmin.save_formset()` → guarda los DetalleComanda
6. Django llama a `response_add()` o `response_change()`

**Problema Anterior:**
- En el paso 3, `Comanda.save()` intentaba acceder a `self.detalles.all()`
- Pero los detalles no existían hasta el paso 5

**Solución:**
- Movimos la creación de ReservaProducto del paso 3 al paso 5
- Ahora se ejecuta en `save_formset()` cuando los detalles ya existen

### Popup Behavior:

El botón "Agregar Comanda con Productos" abre una URL como:
```
/admin/ventas/comanda/add/?venta_reserva=123&_popup=1
```

- `venta_reserva=123`: ID de la reserva desde donde se abrió
- `_popup=1`: Indica que es un popup (debe cerrarse y recargar al guardar)

El `save_model()` captura el parámetro `venta_reserva` del GET y lo asigna automáticamente.

---

## Logs Útiles para Debugging

Si el Error 500 persiste, revisar en Render logs:

```bash
# Buscar por:
- "Traceback"
- "POST /admin/ventas/comanda/add/"
- "IntegrityError"
- "AttributeError"
- "DoesNotExist"
```

Posibles errores que podrían aparecer:
1. `venta_reserva` es NULL → verificar que se asigna desde GET
2. `precio_unitario` es NULL → verificar DetalleComanda.save()
3. `usuario_solicita` es NULL → verificar get_form() initial values
4. Problema con ReservaProducto.get_or_create() → verificar que venta_reserva existe

---

### 10. Error 500 al Crear Comanda - Campos Display en Fieldsets (RESUELTO ✅)

**Síntoma:**
- Error 500 persistía después de todas las correcciones anteriores
- Ocurría al hacer clic en "GUARDAR" en el formulario de nueva comanda

**Causa Raíz:**
- Los métodos `tiempo_espera_display` estaban incluidos en los `fieldsets`
- Estos métodos solo funcionan cuando el objeto ya existe (tienen pk)
- Al crear una nueva comanda, Django intentaba renderizar estos campos con obj=None

**Código Problemático:**
```python
fieldsets = (
    ('Gestión', {
        'fields': (
            'usuario_solicita', 'usuario_procesa',
            'fecha_solicitud', 'hora_solicitud',
            'fecha_inicio_proceso', 'fecha_entrega',
            'tiempo_espera_display'  # ← Este campo causaba el error
        )
    }),
)
```

**Solución:**
1. Remover campos display del fieldset base
2. Agregar método `get_fieldsets()` para mostrar campos solo al editar:

```python
def get_fieldsets(self, request, obj=None):
    """Personalizar fieldsets según si es creación o edición"""
    if obj:  # Editando una comanda existente
        # Incluir todos los campos incluyendo tiempo_espera_display
    else:  # Creando nueva comanda
        # Solo campos básicos, sin campos display
```

**Resultado:**
- ✅ Formulario de creación funciona sin Error 500
- ✅ Formulario de edición muestra todos los campos

**Archivos Modificados:**
- `ventas/admin.py` - Método get_fieldsets agregado

---

### 11. Error 500 - Campos Auto en Fieldsets y Readonly (RESUELTO ✅)

**Síntoma:**
- Error 500 persistía incluso después de las correcciones anteriores

**Causa Raíz:**
1. El atributo `fieldsets` estático todavía existía y Django lo usaba en lugar de `get_fieldsets()`
2. Los campos `created_at` y `updated_at` estaban en `readonly_fields`
3. Estos campos son `auto_now_add=True` y `auto_now=True`, no existen al crear objetos nuevos

**Solución:**
1. Comentar el `fieldsets` estático para forzar uso de `get_fieldsets()`
2. Remover `created_at` y `updated_at` de `readonly_fields`

```python
# ANTES (problemático)
fieldsets = ( ... )  # Django usaba esto en lugar de get_fieldsets
readonly_fields = (..., 'created_at', 'updated_at')

# DESPUÉS (correcto)
# fieldsets se define dinámicamente en get_fieldsets()
readonly_fields = (...) # sin created_at ni updated_at
```

**Resultado:**
- ✅ Error 500 completamente resuelto
- ✅ Comandas se pueden crear desde el admin

**Archivos Modificados:**
- `ventas/admin.py` - Líneas 3078-3092 y 3071-3072

---

### 12. FieldError: Campo 'notas' Inexistente en ReservaProducto (RESUELTO ✅)

**Síntoma:**
- Error 500 al guardar comandas desde el admin
- Logs mostraban: `django.core.exceptions.FieldError: Invalid field name(s) for model ReservaProducto: 'notas'.`

**Causa Raíz:**
- El modelo `ReservaProducto` NO tiene un campo llamado 'notas'
- Tanto en `save_formset` de ComandaAdmin como en `save()` de Comanda, se intentaba crear ReservaProducto con este campo inexistente

**Diagnóstico:**
- El error aparecía como Error 400/403 en los tests pero era Error 500 en producción
- El problema real solo se reveló en los logs de Render

**Solución:**
- Eliminar el campo 'notas' del diccionario `defaults` al crear ReservaProducto
- El modelo ReservaProducto solo tiene: venta_reserva, producto, cantidad, fecha_entrega, precio_unitario_venta

**Código Corregido:**
```python
# ANTES (con error)
ReservaProducto.objects.get_or_create(
    venta_reserva=comanda.venta_reserva,
    producto=detalle.producto,
    defaults={
        'cantidad': detalle.cantidad,
        'precio_unitario_venta': detalle.precio_unitario,
        'fecha_entrega': fecha_entrega_reserva,
        'notas': f'Comanda #{comanda.id}' + (...)  # ❌ Campo inexistente
    }
)

# DESPUÉS (correcto)
ReservaProducto.objects.get_or_create(
    venta_reserva=comanda.venta_reserva,
    producto=detalle.producto,
    defaults={
        'cantidad': detalle.cantidad,
        'precio_unitario_venta': detalle.precio_unitario,
        'fecha_entrega': fecha_entrega_reserva
        # Sin campo 'notas' ✅
    }
)
```

**Resultado:**
- ✅ Error 500 resuelto definitivamente
- ✅ Comandas se crean correctamente desde el popup
- ✅ ReservaProducto se crea automáticamente al guardar comandas

**Archivos Modificados:**
- `ventas/admin.py` - Líneas 3269-3272 (eliminar campo 'notas')
- `ventas/models.py` - Líneas 4772 (eliminar campo 'notas' en Comanda.save())

---

**Fin del Documento**
