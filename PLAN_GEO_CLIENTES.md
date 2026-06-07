# Plan: Clasificación geográfica del cliente desde la venta

**Problema:** la segmentación `region_geografica` (`sur` / `nacional` / `extranjero`) es un campo *derivado* que hoy NO se calcula al momento de la venta. Solo lo llena un comando manual (sin cron) o clics del operador. Resultado: muchos clientes quedan `sin_clasificar`, y la fidelización (WhatsApp "Vuelta a Casa", emails de masaje) se contamina con clientes de zona equivocada.

**Principio rector:** la zona se **deriva automáticamente** de datos estructurados (comuna/país) en **un solo lugar**, y se **captura en todos los puntos de venta**. El texto libre deja de ser la fuente.

**Fuente única de verdad:** catálogo `Ciudad` (nombre_canonico + aliases + region_geografica) + árbol `Región → Comuna`.
**Regla:** país ≠ Chile → `extranjero`; ciudad/comuna en el set sur (≤120 km Puerto Varas) → `sur`; cualquier otra comuna/ciudad chilena → `nacional`; sin datos → `sin_clasificar`.

---

## E0 — Fundación: función única de clasificación + derivación automática *(sin UI)*  ✅ EN CURSO
- Servicio reutilizable `ventas/services/geo_service.py`: `clasificar(pais, ciudad_texto, comuna, region)` → `(metodo, ciudad_normalizada, region_geografica)`.
- **Mejora clave:** clasificar también por **comuna estructurada** y marcar `nacional` (antes quedaban `sin_clasificar` las ciudades chilenas no-sur, ej. "Olmué").
- **Hook automático en `Cliente.save()`**: deriva la zona al guardar, solo si `ciudad_normalizada_manual=False`, y **nunca degrada** (no borra una clasificación existente).
- El comando `normalizar_ciudades_clientes` pasa a usar el mismo servicio (una sola lógica).
- Migración: ninguna. Riesgo: bajo (aditivo, respeta ediciones manuales, try/except que nunca bloquea el guardado).

## E1 — Recepción / Admin (alta nueva + edición + alta rápida desde la venta)
> El form de **Agregar cliente** y **Modificar cliente** es el mismo `ClienteAdmin`; el botón "+" de la venta lo reutiliza. Una sola mejora cubre los tres casos.
- Rediseñar el bloque "Ubicación": **Comuna** como campo principal (buscador), país, y mostrar la **Zona derivada** (sur/nacional/…) como dato visible, con override manual. Eliminar la inconsistencia de 3 campos sueltos (ciudad libre + region + comuna) que no se hablan.
- En "Modificar venta/reserva": mostrar la Zona en el panel "Ficha del cliente" y **avisar si falta**.

## E2 — Checkout web
- Región/Comuna **obligatorias** (o autocompletar de ciudad). La zona se deriva sola (E0).

## E3 — Ficha de masaje (pública)
- Agregar **comuna/ciudad** al formulario. La zona se deriva al crear el cliente.

## E4 — WhatsApp (inbound + bandeja)
- Inbound seguirá con nombre+teléfono; mejorar la clasificación manual en la bandeja. E0 + cron (E5) reducen el residuo.

## E5 — Backfill + automatización + reporte
- Backfill con `--dry-run` y revisión del residuo (prioridad por valor/recencia).
- Cron diario `normalizar_ciudades_clientes --solo-sin-clasificar`.
- Indicador de % clasificado.

## E6 — Calidad de datos
- Aliases de typos (`puerto mont`, `sanstiago`, …); validaciones de combinaciones inconsistentes; plan para deprecar `ciudad` (texto libre) en favor de comuna.

---

| Etapa | Resuelve | Riesgo | Migración |
|---|---|---|---|
| E0 | Derivación automática única | Bajo | No |
| E1 | Recepción admin (alta+edición) + inconsistencia | Bajo | No |
| E2 | Checkout web | Medio | No |
| E3 | Ficha de masaje | Bajo | No |
| E4 | WhatsApp / bandeja | Bajo | No |
| E5 | Backfill + cron + reporte | Bajo | No |
| E6 | Calidad de datos | Bajo | Posible |

**Resguardos:** respaldos de BD (Render) y app (Mac) tomados; todo aditivo; respeta `ciudad_normalizada_manual`; se valida con `--dry-run` y en shell; migraciones (si surgen) a mano en Render.
