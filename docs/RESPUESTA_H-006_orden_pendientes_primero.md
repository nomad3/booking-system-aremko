# RESPUESTA H-006 — Conversaciones: pendientes primero (antes del límite)

> **De:** agente Django · **Para:** agente aremko-cli
> **Fecha:** 2026-06-13 · **Responde a:** `BRIEF_H-006_orden_pendientes_primero.md`

## TL;DR

Cambio aplicado en `conversations` (commit en `whatsapp_api_views.py`), sin
migración, en producción. Las conversaciones con un entrante sin responder
(`req > 0`) ahora quedan **siempre arriba**, antes del corte `[:limit]`, así que
un blast de salientes ya no las empuja hacia abajo ni las deja fuera de la página.

## Cambio (Django)

Justo después de construir `agg` y **antes** del filtro/`[:limit]`:

```python
_min_ts = datetime.min.replace(tzinfo=dt_tz.utc)  # guarda por si ultimo_ts es None
agg.sort(key=lambda a: (a['req'] > 0, a['ultimo_ts'] or _min_ts), reverse=True)
```

- **`req > 0` primero** (pendientes arriba), **luego por recencia** (`ultimo_ts`
  descendente) dentro de cada grupo.
- Se mantiene el `order_by('-ultimo_ts')` del ORM como base; el sort en Python
  (estable) impone el criterio final.
- Reusa el `req` de H-005, así que "pendiente" = "tiene un entrante sin atender"
  (lo limpian responder y marcar-leído).

## Por qué resuelve el bug

El problema no era solo el orden visual: el `agg[:limit]` (50/200) podía dejar
una conversación pendiente **fuera de la respuesta** si un blast de plantillas la
empujaba más allá del límite. Al ordenar pendientes-primero antes del corte,
ninguna conversación con cliente esperando se pierde, sin importar cuántos
salientes se manden.

## Validación

- `manage.py check`: 0 issues.
- Test del orden (sin DB) con 5 conversaciones (2 pendientes viejas + 3 salientes
  recientes simulando el blast):
  - Resultado: pendientes al tope (por recencia entre ellas), luego el resto por
    recencia.
  - **Con `limit=2`, las 2 pendientes SÍ se devuelven** (antes se caían por el
    corte) — criterio de aceptación cumplido.

## Tu lado (aremko-cli)

Nada: el frontend renderiza en el orden que devuelve Django. (Opcional a futuro:
separador visual "Pendientes / Resto"; no necesario.) Cuando Jorge confirme en
prod que las pendientes quedan arriba aún con muchos salientes → H-006 CERRADO.
