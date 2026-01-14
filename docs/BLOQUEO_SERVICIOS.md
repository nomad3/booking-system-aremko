# Sistema de Bloqueo de Servicios

## Descripción

El sistema de bloqueo de servicios permite marcar servicios como "fuera de servicio" por rangos de fechas específicos. Es útil para:

- **Mantenimiento**: Cerrar una tina o cabaña por mantenimiento preventivo
- **Reparaciones**: Bloquear servicio mientras se realizan reparaciones
- **Eventos especiales**: Reservar servicios para uso exclusivo
- **Temporada baja**: Cerrar servicios temporalmente

## Características Principales

### ✅ Validación Automática
- Solo permite bloquear fechas SIN reservas existentes
- Si hay reservas, muestra error con las fechas conflictivas
- Protege contra pérdida de ingresos por bloqueos accidentales

### 🎨 Visualización en Calendario Matriz
- Servicios bloqueados aparecen en **color morado**
- Texto: **"🚫 Fuera de servicio"**
- Muestra el motivo del bloqueo
- Funciona en desktop y móvil

### 🚫 Prevención de Reservas
- Clientes NO pueden reservar servicios bloqueados desde la web
- API retorna horarios vacíos para fechas bloqueadas
- Validación en múltiples puntos del flujo de compra

### 📅 Soporte de Rangos de Fechas
- Bloquear por día único o rangos completos (ej: una semana)
- Todos los slots horarios del servicio quedan bloqueados
- Fechas inclusive (fecha_inicio y fecha_fin incluidas)

## Cómo Usar el Sistema

### 1. Crear un Bloqueo

1. Ir al Django Admin: `/admin/`
2. Buscar **"Bloqueos de Servicios"** en la sección Ventas
3. Hacer clic en **"Agregar bloqueo de servicio"**
4. Completar el formulario:
   - **Servicio**: Seleccionar el servicio a bloquear (ej: Tina Hornopiren)
   - **Fecha inicio**: Primer día del bloqueo (inclusive)
   - **Fecha fin**: Último día del bloqueo (inclusive)
   - **Motivo**: Razón del bloqueo (ej: "Mantenimiento preventivo", "Reparación de bomba")
   - **Activo**: Dejar marcado (desmarcar para desactivar sin eliminar)
   - **Notas** (opcional): Información adicional interna

5. Hacer clic en **"Guardar"**

### 2. Validación Automática

Al guardar, el sistema verifica:

✅ **Si NO hay reservas**: El bloqueo se crea exitosamente

❌ **Si HAY reservas**: Muestra error como:
```
No se puede bloquear: existen 3 reservas en las fechas:
15/01/2026, 17/01/2026, 20/01/2026
```

**Solución**:
- Ajustar las fechas para evitar días con reservas, O
- Cancelar/mover las reservas existentes primero

### 3. Verificar Bloqueos Activos

En el listado de bloqueos verás:

| Servicio | Fecha Inicio | Fecha Fin | Días | Motivo | Activo | Conflictos |
|----------|--------------|-----------|------|--------|--------|------------|
| Tina Hornopiren | 20/01/2026 | 27/01/2026 | 8 | Mantenimiento | ✓ | ✓ Sin conflictos |

**Indicador de conflictos**:
- **Verde "✓ Sin conflictos"**: No hay reservas en el rango
- **Amarillo con lista**: Hay reservas, revisar antes de modificar

### 4. Modificar un Bloqueo Existente

1. En el listado, hacer clic en el bloqueo a modificar
2. Cambiar las fechas o el motivo
3. Guardar

**IMPORTANTE**: Si cambias las fechas y ahora incluyen días con reservas, el sistema NO permitirá guardar.

### 5. Desactivar un Bloqueo (Sin Eliminar)

Opción 1 - Individual:
1. Abrir el bloqueo
2. Desmarcar **"Activo"**
3. Guardar

Opción 2 - En lote:
1. En el listado, seleccionar uno o más bloqueos
2. En el menú "Acciones", elegir **"Desactivar bloqueos seleccionados"**
3. Hacer clic en **"Ir"**

### 6. Reactivar un Bloqueo

1. Filtrar por **"Activo: No"** en la barra lateral
2. Abrir el bloqueo inactivo
3. Marcar **"Activo"**
4. Guardar (se vuelve a validar que no haya reservas)

### 7. Duplicar un Bloqueo

Útil para crear bloqueos recurrentes (ej: mantenimiento semanal):

1. Seleccionar el bloqueo a duplicar
2. En "Acciones", elegir **"Duplicar bloqueo (+7 días)"**
3. Hacer clic en **"Ir"**

El nuevo bloqueo tendrá:
- Mismo servicio y motivo
- Fechas desplazadas +7 días
- Estado activo

### 8. Eliminar un Bloqueo

**RECOMENDADO**: Usar desactivación en lugar de eliminación (mantiene historial)

Si necesitas eliminar permanentemente:
1. Abrir el bloqueo
2. Hacer clic en **"Eliminar"** (botón rojo)
3. Confirmar eliminación

## Qué Sucede Cuando un Servicio Está Bloqueado

### 🟣 Calendario Matriz (Staff)

```
┌─────────────┬─────────────────┬─────────────────┐
│ Horario     │ Tina Hornopiren │ Tina Calbuco    │
├─────────────┼─────────────────┼─────────────────┤
│ 12:00       │ 🚫 Fuera de     │ Disponible      │
│             │ servicio        │                 │
│             │ (Mantenimiento) │                 │
├─────────────┼─────────────────┼─────────────────┤
│ 14:30       │ 🚫 Fuera de     │ Disponible      │
│             │ servicio        │                 │
└─────────────┴─────────────────┴─────────────────┘
```

- **Color morado** distingue claramente de otros estados
- Tooltip muestra rango completo del bloqueo
- NO se pueden crear reservas desde el calendario

### 🌐 Página Web Pública

- Servicio NO aparece en horarios disponibles para esa fecha
- Si cliente intenta forzar la reserva (manipulando URL), recibe error
- Mensaje claro: *"El servicio no está disponible en la fecha seleccionada (fuera de servicio)"*

### 📱 API de Disponibilidad

```json
{
  "success": true,
  "horas_disponibles": [],
  "bloqueado": true
}
```

- Lista de horarios vacía
- Flag `bloqueado: true` para que frontend pueda mostrar mensaje específico

### 🛒 Flujo de Compra

**Al agregar al carrito**:
- Sistema valida antes de agregar
- Redirige con mensaje: *"El servicio 'Tina Hornopiren' no está disponible en la fecha seleccionada (fuera de servicio)"*

**Al finalizar compra (checkout)**:
- Doble validación antes de crear reserva
- Error en JSON: *"Tina Hornopiren no está disponible en 20/01/2026 (fuera de servicio)"*

## Casos de Uso Comunes

### Caso 1: Mantenimiento Semanal de Tina

**Escenario**: Cada lunes la Tina Hornopiren necesita mantenimiento

**Solución**:
1. Crear bloqueo para el próximo lunes (un solo día)
2. Motivo: "Mantenimiento semanal"
3. Usar acción "Duplicar bloqueo (+7 días)" cada semana

### Caso 2: Reparación de Cabaña por 1 Semana

**Escenario**: Cabaña Torre necesita reparaciones del 15 al 22 de enero

**Solución**:
1. Crear bloqueo:
   - Servicio: Cabaña Torre
   - Fecha inicio: 15/01/2026
   - Fecha fin: 22/01/2026
   - Motivo: "Reparación de instalaciones"

2. Si hay reserva el 18/01:
   - Contactar al cliente para mover la reserva
   - Cancelar la reserva en el sistema
   - Crear el bloqueo

### Caso 3: Evento Privado - Reserva Exclusiva

**Escenario**: Cliente corporativo reserva TODAS las tinas para un evento el 10 de febrero

**Opción A - Bloqueo**:
- Bloquear todas las tinas el 10/02
- Crear reserva manual en admin para el cliente corporativo

**Opción B - Reserva Normal** (RECOMENDADO):
- Crear reservas normales para cada tina
- NO usar bloqueo (ya que SÍ se están usando, solo de forma exclusiva)

### Caso 4: Temporada Baja - Cerrar Servicios

**Escenario**: Durante junio-julio, cerrar 2 de 4 tinas para ahorrar costos

**Solución**:
1. Identificar las 2 tinas con menos reservas
2. Crear bloqueos de 1 mes:
   - Fecha inicio: 01/06/2026
   - Fecha fin: 31/07/2026
   - Motivo: "Cerrado por temporada baja"
3. Mantener activas solo 2 tinas principales

## Filtros y Búsqueda

### Filtros Disponibles

En el listado de bloqueos puedes filtrar por:

- **Activo**: Ver solo activos o inactivos
- **Categoría de Servicio**: Tinas, Cabañas, Masajes, etc.
- **Servicio Específico**: Ver bloqueos de un servicio en particular
- **Fecha de Creación**: Por año, mes, día

### Búsqueda

El buscador encuentra bloqueos por:
- Nombre del servicio (ej: "Hornopiren")
- Motivo (ej: "mantenimiento")
- Notas internas

### Jerarquía de Fechas

En la vista de lista, usa la jerarquía de fechas arriba para navegar:
- **2026** → **Enero** → **Semana del 13 al 19**

## Reportes y Estadísticas

### Ver Historial de Bloqueos

1. Ir a **Bloqueos de Servicios**
2. NO filtrar por "Activo" (deja ambos)
3. Ordenar por "Fecha creación" (descendente)

Verás todos los bloqueos históricos, incluyendo:
- Cuándo se creó cada bloqueo
- Quién lo creó (usuario)
- Si está activo o fue desactivado

### Análisis de Días Fuera de Servicio

Para saber cuántos días estuvo bloqueado un servicio:

1. Filtrar por servicio específico
2. Revisar columna "Días bloqueados"
3. Sumar totales manualmente o exportar a Excel

## Preguntas Frecuentes (FAQ)

### ¿Puedo bloquear solo un horario específico?

**NO**. El bloqueo es por día completo. Todos los horarios del servicio quedan bloqueados.

**Alternativa**: Si necesitas bloquear solo algunos slots, crea reservas "dummy" o "mantenimiento" en el admin.

### ¿Qué pasa si ya hay reservas y necesito bloquear urgente?

**Proceso recomendado**:
1. Contactar a los clientes afectados
2. Ofrecer alternativas (otro servicio, otra fecha, reembolso)
3. Cancelar las reservas en el sistema (cambiar estado a "cancelada")
4. AHORA sí podrás crear el bloqueo

### ¿Se notifica automáticamente a los clientes?

**NO**. El sistema de bloqueo NO envía notificaciones automáticas.

**Debes hacerlo manualmente**:
1. Antes de crear un bloqueo que afecte reservas futuras
2. Contactar a los clientes por email/teléfono
3. Luego cancelar las reservas y crear el bloqueo

### ¿Puedo bloquear varios servicios a la vez?

**NO directamente**. Debes crear un bloqueo por cada servicio.

**Tip**: Usa la acción de duplicar y luego edita el servicio en cada copia.

### ¿Los bloqueos afectan el cálculo de ocupación?

**SÍ**. En el resumen del calendario matriz, los slots bloqueados NO cuentan como "disponibles".

Ejemplo:
- Total slots del día: 100
- Bloqueados: 20
- Ocupados (con reservas): 30
- **Disponibles reales: 50** (no 70)

### ¿Puedo ver qué usuario creó un bloqueo?

**SÍ**. En el detalle del bloqueo, campo **"Creado por"** muestra:
- Nombre del usuario que lo creó
- Fecha y hora exacta de creación

### ¿Cómo saber si un bloqueo está causando problemas?

Revisa el campo **"Ver reservas conflicto"** en el detalle del bloqueo:

- **Verde "✓ Sin conflictos"**: Todo bien
- **Lista de reservas**: Hay reservas activas en esas fechas (puede indicar que el bloqueo se creó después de las reservas, o que hay un problema de validación)

## Migración SQL Manual

### Instalación Inicial (Solo Primera Vez)

**IMPORTANTE**: Esta tabla se crea mediante migración SQL MANUAL en Render.

Si aún no has ejecutado la migración:

1. Abrir Shell en Render (web service)
2. Ejecutar:
   ```bash
   python manage.py dbshell
   ```

3. Copiar y pegar todo el contenido de:
   ```
   migrations_manual/add_servicio_bloqueo_table.sql
   ```

4. Verificar que se creó:
   ```sql
   \dt ventas_serviciobloqueo
   \d ventas_serviciobloqueo
   ```

5. Salir de psql:
   ```
   \q
   ```

6. El modelo ya está en el código, así que NO necesitas `makemigrations` ni `migrate`

### Verificación Post-Migración

Para confirmar que todo funciona:

1. Ir a `/admin/ventas/serviciobloqueo/`
2. Crear un bloqueo de prueba
3. Verificar que aparece en calendario matriz en morado
4. Intentar reservar ese servicio desde la web (debe fallar)

## Soporte Técnico

### Logs de Debugging

Si hay problemas, revisa los logs de Python:

```python
# En availability_views.py verás:
[get_available_hours] Service 123 is BLOCKED on 2026-01-20
```

### Comandos Útiles de Base de Datos

```sql
-- Ver todos los bloqueos activos
SELECT s.nombre, sb.fecha_inicio, sb.fecha_fin, sb.motivo
FROM ventas_serviciobloqueo sb
JOIN ventas_servicio s ON sb.servicio_id = s.id
WHERE sb.activo = true
ORDER BY sb.fecha_inicio;

-- Contar días bloqueados por servicio (mes actual)
SELECT s.nombre,
       COUNT(*) as total_bloqueos,
       SUM(sb.fecha_fin - sb.fecha_inicio + 1) as dias_bloqueados
FROM ventas_serviciobloqueo sb
JOIN ventas_servicio s ON sb.servicio_id = s.id
WHERE sb.activo = true
  AND sb.fecha_inicio >= DATE_TRUNC('month', CURRENT_DATE)
  AND sb.fecha_fin < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
GROUP BY s.nombre
ORDER BY dias_bloqueados DESC;
```

## Mejoras Futuras Posibles

Ideas para expandir el sistema (no implementadas aún):

1. **Notificaciones automáticas** a clientes afectados
2. **Bloqueo de horarios específicos** (no solo días completos)
3. **Bloqueos recurrentes** (ej: "todos los lunes")
4. **Aprobación de bloqueos** (requiere autorización de gerente)
5. **Dashboard de bloqueos** con estadísticas visuales
6. **Export a calendario** (iCal/Google Calendar)

---

**Versión**: 1.0
**Fecha**: Enero 2026
**Contacto**: Equipo de Desarrollo
