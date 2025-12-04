# 🚨 HOTFIX - ERROR 500 EN RESERVAS

## ❗ URGENTE - ACCIÓN INMEDIATA REQUERIDA

### 📋 Problema
Error 500 al agregar personas a reservas de tinas debido al intento de acceder al campo `cantidad_minima_personas` que aún no existe en la base de datos.

### ✅ Solución Aplicada (Commit: 827d822)

El código ahora maneja de forma segura cuando el campo no existe:
- Usa try/except para capturar errores de atributo
- Solo aplica restricciones cuando se requiere más de 1 persona
- Permite funcionamiento normal antes de aplicar migración

## 🔧 PASOS PARA RESOLVER EN PRODUCCIÓN

### Opción 1: SOLUCIÓN INMEDIATA (Sin migración)
```bash
# En la shell de Render
# El código ya está actualizado con el hotfix
# Solo necesitas que Render tome los cambios más recientes

# 1. Verificar que el servicio se reinició con los cambios
# El deploy automático debería hacerse al detectar el push

# 2. Si no se actualizó automáticamente:
# Manual deploy desde el dashboard de Render
```

### Opción 2: SOLUCIÓN COMPLETA (Con migración)
```bash
# Una vez que el error 500 esté resuelto, puedes aplicar la migración

# 1. Aplicar migración
python manage.py migrate ventas 0066

# 2. Actualizar el pack de $35,000 para requerir 2 personas
python manage.py shell

# En el shell:
from ventas.models import PackDescuento

# Buscar packs de Tina + Masaje
packs = PackDescuento.objects.filter(activo=True)
for pack in packs:
    print(f"ID: {pack.id}, Nombre: {pack.nombre}, Descuento: ${pack.valor_descuento}")
    servicios = [s.nombre for s in pack.servicios_requeridos.all()]
    print(f"  Servicios: {servicios}")

# Actualizar el pack específico (reemplaza ID con el correcto)
pack_35k = PackDescuento.objects.get(id=ID_DEL_PACK)  # Usa el ID correcto
pack_35k.cantidad_minima_personas = 2
pack_35k.save()
print(f"✅ Pack actualizado para requerir mínimo 2 personas")

exit()
```

## 🔍 VERIFICACIÓN

### Verificar que NO hay error 500:
1. Ir a la página de tinas
2. Agregar 1 persona a una reserva
3. Debe funcionar sin errores

### Verificar descuentos (después de migración):
1. Con 1 persona en Tina + Masaje: NO descuento
2. Con 2+ personas en Tina + Masaje: SÍ descuento de $35,000

## 📝 NOTAS TÉCNICAS

### Cambios en el código:
```python
# ANTES (causaba error):
cantidad_minima_personas = getattr(pack, 'cantidad_minima_personas', 1)

# DESPUÉS (manejo seguro):
try:
    cantidad_minima_personas = pack.cantidad_minima_personas if hasattr(pack, 'cantidad_minima_personas') else 1
except AttributeError:
    cantidad_minima_personas = 1
```

### Por qué funciona:
- `hasattr()` verifica si el atributo existe
- `try/except` captura cualquier AttributeError
- Valor por defecto = 1 (no restricción)
- Solo aplica restricción si cantidad_minima_personas > 1

## 🎯 ESTADO ACTUAL

- ✅ Hotfix aplicado (commit 827d822)
- ✅ Código actualizado en GitHub
- ⏳ Esperando deploy automático en Render
- ⏳ Migración 0066 pendiente de aplicar

---

**IMPORTANTE**: Este hotfix permite que el sistema funcione inmediatamente sin la migración. La migración puede aplicarse cuando sea conveniente sin presión de tiempo.