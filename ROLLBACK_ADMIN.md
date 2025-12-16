# Plan de Rollback de Emergencia

## Si necesitas revertir los cambios del admin inmediatamente:

### Opción 1: Revertir el commit del admin (más rápido)

```bash
git revert 96c3a99 e6ce2eb --no-edit
git push
```

Esto revertirá:
- `96c3a99` - fix: mejorar manejo de excepciones en admin de categorías
- `e6ce2eb` - feat: agregar gestión de imágenes hero en admin de categorías

### Opción 2: Volver a registro simple de CategoriaServicio

Editar `ventas/admin.py` línea 356 y cambiar:

```python
@admin.register(CategoriaServicio)
class CategoriaServicioAdmin(admin.ModelAdmin):
    # ... todo el código ...
```

Por:

```python
admin.site.register(CategoriaServicio)
```

Y eliminar todo el código de la clase `CategoriaServicioAdmin`.

También eliminar los cambios en `SEOContentAdmin` (revertir a la versión anterior).

### Opción 3: Ejecutar diagnóstico primero

```bash
# En el shell de Render
python scripts/diagnose_error.py
```

Esto te dirá exactamente qué está fallando.

---

## URLs de commits para referencia:

- Antes de los cambios del admin: `b7c7ffb`
- Después de agregar admin: `e6ce2eb`
- Después del fix: `96c3a99`
- Diagnóstico agregado: `964b735`

Para volver al estado antes de los cambios del admin:

```bash
git revert HEAD~3..HEAD --no-edit
git push
```
