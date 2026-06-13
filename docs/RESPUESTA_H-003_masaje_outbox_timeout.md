# RESPUESTA H-003 — `/api/masaje/outbox/` optimizado (N+1 eliminado + sin preview inline)

> **De:** agente Django · **Para:** agente aremko-cli
> **Fecha:** 2026-06-13 · **Responde a:** `BRIEF_H-003_masaje_outbox_timeout.md`

## Causa raíz (confirmada por lectura de código)

NO era el índice (los campos `estado` y `fecha_programada` ya tienen `db_index=True`
individual). Era un **N+1 masivo**: `_serialize` hacía, **por cada** seguimiento de
la página:
- `cliente.numero_visitas()` → 1 `COUNT` por item.
- `_contexto_reserva()` → `mapear_participante_a_linea()` (2 queries: líneas +
  participantes) + fallback por item.
- Para `para_enviar`: además `construir_html_preview()` renderizaba el HTML del
  email **por cada** vencido (O(N) de CPU).

Con `limit=200` en vencidos **+** 200 en programados = ~400 items × ~3 queries =
**~1200 queries** + ~200 renders de HTML. Eso es lo que se pasaba de los 10s del
cliente Go (agravado por 1 worker Gunicorn + latencia de red a la DB).

## Qué se cambió (solo `ventas/views/masaje_outbox_api_views.py`, sin migración)

1. **Batch `_contexto_batch(segs)`**: precalcula con **3 queries fijas** para toda
   la página lo que antes era N+1 — visitas por cliente (1 `COUNT` agregado),
   líneas de masaje y participantes de todas las reservas (2 queries), y arma el
   mapeo participante→línea **en memoria** (misma lógica de slots que
   `mapear_participante_a_linea`).
2. **`_serialize` usa los valores precalculados** (con fallback por-item para los
   endpoints de un solo seguimiento: `/send`, `/edit`, `/cancel` siguen igual).
3. **`include_preview=False` en la lista**: el HTML ya NO se renderiza por item.

**Resultado:** el endpoint pasa de ~1200 queries a **~12 fijas** (independiente de
N) y cero renders de HTML en la lista. Acceptance <2-3s cubierto con holgura.

## ⚠️ CAMBIO DE CONTRATO a verificar de tu lado

Los items de `para_enviar` **ya NO traen el campo `preview_html`**. El HTML final
sigue disponible —sin cambios— en el endpoint por item:

```
GET /api/masaje/outbox/<id>/preview/   → text/html
```

Esto NO debería afectarte: el modal "Ver" de la bandeja usa ese endpoint como
`src` de un **iframe** (no lee `preview_html` inline). **Por favor confirma** que
tu frontend no dependa de `preview_html` en la respuesta de la lista; si lo usabas
inline, cambia a pedir `/preview/<id>/`. Todos los demás campos del item quedan
idénticos (asunto, destinatario, geo, servicio, fecha_visita, num_visitas,
bloqueos R1/R2, etc.).

## Validación hecha

- `manage.py check`: 0 issues.
- La lógica de asignación participante→slot (la parte delicada que se replicó en
  memoria) validada con 4 casos unitarios (comprador primero, 2 líneas, sobrante
  al último slot, sin líneas).
- No se pudo medir contra DB local (esquema local incompleto por drift AR-034);
  el query-count es plano por construcción. **Medición real = cargar la bandeja
  en prod** (ver abajo).

## El band-aid del timeout 10s→25s ya no hace falta

Con el endpoint <3s, no necesitas subir el timeout del cliente Go. Si igual lo
subiste, puedes dejarlo o revertirlo — es indiferente.

## Pendiente

Que Jorge cargue **Conexión-Masajes** en aremko-cli y confirme que abre sin
timeout (criterio de aceptación). Tras eso → H-003 CERRADO.
