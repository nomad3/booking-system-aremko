# Documentación: Error del Calendario con Servicios de Masajes

**Fecha:** 2026-02-18
**Problema:** El calendario funciona correctamente para Tinas y Cabañas pero falla con Masajes

---

## Error Principal

```
Error: 'ServicioSlotBloqueo' object has no attribute 'notas'
```

Ubicación del error:
- Archivo: `/app/ventas/views/calendario_matriz_view.py`
- Línea: 452
- Código problemático: `bloqueo_slot.notas`

---

## Diagnóstico Inicial

1. **Servicios que funcionan:**
   - ✅ Tinas
   - ✅ Cabañas
   - ❌ Masajes (error)

2. **Causa identificada:**
   - El modelo `ServicioSlotBloqueo` NO tiene el campo 'notas' en models.py
   - La base de datos SÍ tiene la columna 'notas'
   - Desincronización entre modelo Django y esquema de BD

3. **Por qué funciona para algunos servicios:**
   - Posiblemente los masajes son los únicos que tienen `ServicioSlotBloqueo` con datos
   - O usan una ruta de código diferente en el calendario

---

## Intentos de Solución

### 1. Agregar columnas faltantes a la BD (COMPLETADO ✅)

Se ejecutaron múltiples scripts para agregar columnas faltantes:

```bash
# Script fix_all_calendar_columns.py
- Agregó created_at, updated_at a varias tablas
- Agregó fecha, hora, estado a ventas_ventareserva
- Todas las columnas se agregaron exitosamente
```

### 2. Agregar campo 'notas' al modelo ServicioSlotBloqueo (MÚLTIPLES INTENTOS)

#### Intento A: Script add_notas_to_model.py
```python
# Intentaba agregar automáticamente el campo al modelo
# Resultado: Se ejecutó pero Django no reconoció el campo
```

#### Intento B: Modificación manual con sed
```bash
# En línea 4847 de models.py después de updated_at
sed -i '4847 a\    notas = models.TextField(blank=True, null=True)' /app/ventas/models.py

# Verificación:
sed -n '4837,4855p' /app/ventas/models.py
# Resultado: Campo agregado correctamente en el archivo
```

#### Problemas encontrados:
- Después de reiniciar, Django seguía sin reconocer el campo
- Al hacer deploy manual, los cambios se perdieron (no estaban en git)

### 3. Modificar el código del calendario (INTENTO ACTUAL)

#### Cambio aplicado:
```python
# ANTES (línea 452):
'notas_bloqueo': bloqueo_slot.notas if bloqueo_slot.notas else None,

# DESPUÉS:
'notas_bloqueo': getattr(bloqueo_slot, 'notas', None),
```

#### Comandos ejecutados:
```bash
# Primer intento con sed global
sed -i "s/bloqueo_slot\.notas/getattr(bloqueo_slot, 'notas', '')/g" /app/ventas/views/calendario_matriz_view.py

# Segundo intento más específico
sed -i '452s/.*/                        '"'"'notas_bloqueo'"'"':getattr(bloqueo_slot, '"'"'notas'"'"', None),/' /app/ventas/views/calendario_matriz_view.py
```

**Resultado:** El cambio se aplicó en el archivo pero el error persiste

---

## Acciones de Mantenimiento Realizadas

1. **Limpieza de caché Python:**
```bash
find /app -name "*.pyc" -delete
find /app -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
```

2. **Reinicios de aplicación:**
```bash
kill 1  # Múltiples veces
# También se hizo deploy manual y clear cache desde Render
```

3. **Respaldos creados:**
- Respaldo de aplicación: `/tmp/backup_app_20260218_141517`
- Export de BD: `aremko_db_produccion` (18 feb 2026)
- Respaldos anteriores disponibles del 11 feb 2026

---

## Estado Actual del Sistema

### Base de Datos
- **Producción:** `aremko_db_produccion`
- **Otra BD:** `aremko_db_prod` (posiblemente desarrollo)
- La columna 'notas' EXISTE en la tabla ventas_servicioslotbloqueo

### Modelo Django (ServicioSlotBloqueo)
```python
class ServicioSlotBloqueo(models.Model):
    servicio = models.ForeignKey('Servicio', on_delete=models.CASCADE, related_name='slots_bloqueados')
    fecha = models.DateField()
    hora_slot = models.CharField(max_length=5)
    motivo = models.CharField(max_length=200)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # FALTA: notas = models.TextField(blank=True, null=True)
```

### Código del Calendario (línea 452)
- Actualmente tiene: `'notas_bloqueo':getattr(bloqueo_slot, 'notas', None),`
- Debería manejar el campo faltante pero el error persiste

---

## Problemas No Resueltos

1. **¿Por qué funciona para algunos servicios pero no para masajes?**
   - No se investigó completamente la diferencia
   - Posible diferencia en tipo_servicio o en cómo se consultan

2. **¿Por qué getattr() no está funcionando?**
   - El código muestra getattr pero el error persiste
   - Posible caché o el error viene de otro lugar

3. **Problemas con Git:**
   - No se pudieron hacer commits durante toda la sesión
   - Los cambios en el servidor no persisten después de deploys

---

## Scripts Creados Durante la Sesión

1. `check_serviciobloqueo.py` - Diagnóstico inicial
2. `fix_serviciobloqueo.py` - Agregar columna fecha
3. `check_calendario_code.py` - Verificar código del calendario
4. `check_models_confusion.py` - Verificar confusión de modelos
5. `fix_calendar_model_issue.py` - Agregar hora_slot
6. `fix_servicioslotbloqueo_created_at.py` - Agregar created_at
7. `check_all_calendar_tables.py` - Verificación completa
8. `fix_all_calendar_columns.py` - Arreglar todas las columnas
9. `fix_servicioslotbloqueo_notas.py` - Intento de arreglar notas
10. `add_notas_column.py` - Agregar columna notas
11. `add_notas_to_model.py` - Agregar campo al modelo
12. `fix_notas_properly.py` - Otro intento de fix
13. `check_and_fix_all_notas.py` - Búsqueda y reemplazo global
14. `verify_notas_field.py` - Verificación del campo
15. `diagnose_notas_issue.py` - Diagnóstico completo
16. `check_masajes.py` - Investigar servicios de masaje
17. `check_current_db.py` - Verificar BD en uso

---

## Próximos Pasos Recomendados

1. **Investigar la diferencia entre servicios:**
   - ¿Qué tienen de especial los masajes?
   - ¿Usan un tipo_servicio diferente?
   - ¿Hay una consulta especial para ellos?

2. **Buscar TODOS los accesos a .notas:**
```bash
grep -r "\.notas" /app/ventas/ --include="*.py"
```

3. **Considerar revertir a un respaldo:**
   - Tenemos respaldo del 11 de febrero (antes de cambios)
   - Evaluar si vale la pena volver atrás

4. **Solución definitiva:**
   - Agregar el campo 'notas' al modelo en el código fuente
   - Hacer commit y deploy apropiado
   - O eliminar todas las referencias a 'notas' del calendario

5. **Verificar logs de errores:**
   - El error real podría estar en otro lugar
   - Revisar logs completos de Render

---

## Notas Importantes

- **Migraciones deshabilitadas:** El proyecto tiene las migraciones automáticas deshabilitadas
- **Problemas de sincronización:** Existe desincronización entre modelos Django y esquema de BD
- **Git no funcional:** Durante toda la sesión no se pudieron hacer commits
- **Cambios no persisten:** Los cambios hechos directamente en el servidor se pierden con deploys

---

**Última actualización:** 2026-02-18 22:35 (hora local)