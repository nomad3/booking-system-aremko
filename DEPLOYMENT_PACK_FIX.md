# 🔧 INSTRUCCIONES DE DESPLIEGUE - FIX PACK DESCUENTOS

## 📝 RESUMEN DEL CAMBIO
Se ha corregido el problema donde el descuento de $35,000 (Tina + Masaje) se aplicaba incorrectamente a 1 persona cuando debería requerir mínimo 2 personas.

## 🚀 PASOS DE DESPLIEGUE EN RENDER

### Paso 1: Acceder a la Shell de Render
```bash
# En el dashboard de Render, ir a tu servicio
# Click en "Shell" en la barra lateral
```

### Paso 2: Aplicar la Migración
```bash
# Verificar migraciones pendientes
python manage.py showmigrations ventas

# Aplicar la nueva migración
python manage.py migrate ventas 0066

# Verificar que se aplicó correctamente
python manage.py showmigrations ventas | grep 0066
```

### Paso 3: Actualizar los Packs Existentes
```bash
# Ejecutar el comando para configurar los packs
python ventas/management/commands/update_pack_minimo_personas.py

# Este comando:
# - Busca el pack con descuento de $35,000
# - Lo actualiza para requerir mínimo 2 personas
# - Muestra un resumen de todos los packs
```

### Paso 4: Verificación Manual (Opcional)
```bash
# Acceder al shell de Django
python manage.py shell

# Verificar el pack específico
from ventas.models import PackDescuento
pack = PackDescuento.objects.filter(valor_descuento=35000).first()
print(f"Pack: {pack.nombre}")
print(f"Descuento: ${pack.valor_descuento}")
print(f"Mínimo personas: {pack.cantidad_minima_personas}")

# Salir del shell
exit()
```

## 🔍 VERIFICACIÓN EN PRODUCCIÓN

### 1. Probar con 1 persona:
- Agregar Tina + Masaje para 1 persona
- Verificar que NO se aplica el descuento de $35,000

### 2. Probar con 2+ personas:
- Agregar Tina + Masaje para 2 o más personas
- Verificar que SÍ se aplica el descuento de $35,000

## 📊 CAMBIOS REALIZADOS

### Archivos Modificados:
1. **ventas/models.py**
   - Añadido campo `cantidad_minima_personas` a PackDescuento

2. **ventas/services/pack_descuento_service.py**
   - Actualizada validación para verificar cantidad mínima de personas

3. **ventas/migrations/0066_packdescuento_cantidad_minima_personas.py**
   - Nueva migración para agregar el campo

4. **ventas/management/commands/update_pack_minimo_personas.py**
   - Comando para actualizar packs existentes

## 🛠️ CONFIGURACIÓN EN DJANGO ADMIN

Después del despliegue, puedes ajustar la configuración de cualquier pack desde el admin:

1. Ir a `/admin/`
2. Navegar a **Ventas → Packs de descuento**
3. Editar el pack deseado
4. Ajustar el campo **"Cantidad mínima de personas"**
5. Guardar cambios

## ⚠️ NOTAS IMPORTANTES

- El valor por defecto para packs existentes será 1 persona
- Solo el pack de $35,000 se actualiza automáticamente a 2 personas
- Puedes modificar cualquier pack desde el admin después de la migración

## 📝 ROLLBACK (Si es necesario)

Si necesitas revertir los cambios:
```bash
# En la shell de Render
python manage.py migrate ventas 0065

# Esto revertirá la migración 0066
```

---

**Commit**: `b450540` - fix: agregar validación de cantidad mínima de personas para packs de descuento