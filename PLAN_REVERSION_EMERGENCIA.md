# 🚨 PLAN DE REVERSIÓN DE EMERGENCIA

## SI EL DEPLOY ACTUAL NO FUNCIONA, EJECUTAR ESTO:

### ✅ PUNTO DE REVERSIÓN SEGURO
**Commit estable**: `696c28f` (2 de diciembre - "fix: remove collapse class from SEO admin fieldsets")
- Este fue el último commit antes de todos los cambios de packs y descuentos
- El sistema funcionaba perfectamente en este punto

## 🔄 COMANDOS DE REVERSIÓN

### Opción 1: REVERSIÓN SUAVE (Recomendada)
```bash
# Esto crea un nuevo commit que deshace todos los cambios
git revert --no-commit b41325d..696c28f
git commit -m "revert: volver al estado estable antes de cambios de packs"
git push origin main
```

### Opción 2: REVERSIÓN DIRECTA (Más agresiva)
```bash
# Esto mueve el código al estado exacto del 2 de diciembre
git reset --hard 696c28f
git push --force origin main
```

## 📋 QUÉ SE REVERTIRÁ

### Cambios que se eliminarán:
1. Toda la lógica de validación de cantidad mínima de personas
2. El campo cantidad_minima_personas
3. La migración 0066
4. Todos los fixes intentados

### Lo que quedará:
- Sistema funcionando como el 2 de diciembre
- Sin validación de personas mínimas
- Sin restricciones especiales para el pack de $35,000
- PERO SIN ERROR 500

## 🎯 DESPUÉS DE REVERTIR

1. El sistema volverá al comportamiento anterior:
   - Los descuentos se aplicarán sin importar cantidad de personas
   - No habrá error 500
   - Todo funcionará como antes

2. Se puede planificar con calma una solución mejor:
   - Aplicar primero la migración en producción
   - Luego actualizar el código
   - Probar en staging antes de producción

## ⚠️ IMPORTANTE

**Si decides revertir:**
- El pack de $35,000 se aplicará incluso con 1 persona
- PERO el sistema funcionará sin errores
- Es mejor tener el descuento aplicándose incorrectamente que tener el sitio caído

---

**COMANDO RECOMENDADO SI HAY QUE REVERTIR:**
```bash
git revert --no-commit b41325d..696c28f && git commit -m "revert: volver al estado estable del 2 de diciembre - sistema funcionando sin error 500" && git push origin main
```