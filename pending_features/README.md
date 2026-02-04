# 📁 Archivos Pendientes de Implementación

Este directorio contiene funcionalidades que están desarrolladas pero no implementadas en producción.

## Estado: PENDIENTE DE IMPLEMENTACIÓN

### 1. `0059_add_periodic_task_frequencies.py`

**Tipo:** Migración de Django
**Módulo:** Control de Gestión
**Fecha:** Febrero 2026

**Descripción:**
- Agrega funcionalidad de tareas periódicas programables
- Permite configurar tareas con frecuencias: diaria, semanal, mensual, trimestral, semestral, anual
- Útil para automatizar tareas operativas recurrentes

**Para implementar:**
```bash
# 1. Copiar al directorio de migraciones
cp pending_features/0059_add_periodic_task_frequencies.py control_gestion/migrations/

# 2. Ejecutar migración
python manage.py migrate control_gestion

# 3. Probar funcionalidad
```

### 2. `create_tramos_migration.py`

**Tipo:** Comando de gestión
**Módulo:** Ventas
**Fecha:** Febrero 2026

**Descripción:**
- Comando auxiliar para crear migración de sistema de premios
- Actualiza de tramo único a múltiples tramos válidos
- Permite premios que apliquen a rangos de tramos

**Para implementar:**
```bash
# 1. Copiar al directorio de comandos
cp pending_features/create_tramos_migration.py ventas/management/commands/

# 2. Ejecutar comando
python manage.py create_tramos_migration

# 3. Ejecutar la migración generada
python manage.py migrate ventas
```

## ⚠️ Notas Importantes

1. **No subir a producción** sin pruebas exhaustivas
2. **Hacer backup** de la base de datos antes de implementar
3. **Revisar dependencias** de otras migraciones
4. **Probar en ambiente de desarrollo** primero

## 📋 Checklist Pre-Implementación

- [ ] Revisar que no hay conflictos con migraciones actuales
- [ ] Hacer backup de base de datos
- [ ] Probar en desarrollo local
- [ ] Probar en staging (si existe)
- [ ] Documentar cambios en CHANGELOG
- [ ] Actualizar documentación de usuario si es necesario

---

**Última actualización:** Febrero 2026