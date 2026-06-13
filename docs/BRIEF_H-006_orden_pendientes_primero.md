# BRIEF H-006 — Ordenar conversaciones: pendientes primero (antes del límite)

- **Solicita:** agente aremko-cli (a pedido de Jorge)
- **Implementa:** Django (lógica de orden en `conversations`)
- **Fecha:** 2026-06-13
- **Estado:** SOLICITADO

## Necesidad (de Jorge)

La bandeja ordena por recencia. Si se mandan **muchas plantillas salientes** (ej. una campaña
de 100), esas conversaciones saltan al tope por su timestamp y una con un **entrante sin
responder** se hunde — y peor, **puede caerse del listado** por el corte `[:limit]`. Jorge quiere
que las **pendientes queden siempre primero**, automáticamente.

## Diagnóstico (desde aremko-cli)

En `ventas/views/whatsapp_api_views.py` → `conversations` (L497+):
```python
agg = list(WhatsAppMessage.objects.values('phone').annotate(
    ultimo_ts=Max('timestamp'), ..., req=Count('id', filter=Q(direction='in', requiere_atencion=True)),
).order_by('-ultimo_ts'))          # ① ordena solo por recencia (entrante O saliente)
...
if solo_pendientes: agg = [a for a in agg if _pendiente(a)]
page = agg[:limit]                  # ② corta a limit (default 50, máx 200)
```
- **①** Un saliente (plantilla) actualiza `ultimo_ts` → empuja esa conversación arriba; una pendiente más antigua baja.
- **②** Lo grave: `agg[:limit]`. Si por el blast la pendiente queda en posición > limit, **no se devuelve** (no es que esté abajo: no aparece). El filtro `solo_pendientes` lo mitiga solo en la vista filtrada (filtra antes de cortar), no en la vista normal.

`_pendiente(a)` ya es `a['req'] > 0` (H-005), así que tenemos la señal de pendiente lista.

## Pedido (Django) — cambio chico

Ordenar **pendientes primero**, luego por recencia, **antes** de `[:limit]`:
```python
agg.sort(key=lambda a: (a['req'] > 0, a['ultimo_ts']), reverse=True)
```
(o el equivalente en el `order_by` del ORM). Así una conversación con entrante sin responder
queda siempre arriba y **nunca se cae por el límite**, sin importar cuántos salientes se manden.
Dentro de cada grupo (pendientes / no pendientes) se mantiene el orden por recencia.

## Aceptación

- Con >limit conversaciones y un blast de salientes: una conversación con entrante sin responder
  aparece **al tope** y **se devuelve** en la página (no se pierde por el corte).
- El orden dentro de las pendientes y dentro del resto sigue siendo por recencia.

## Lado aremko-cli

- **Nada**: el frontend renderiza en el orden que devuelve Django. (Opcional a futuro: separador
  visual "Pendientes / Resto"; no necesario para este cambio.)

## Punteros (Django)

- `ventas/views/whatsapp_api_views.py` → `conversations`: `order_by('-ultimo_ts')` (~L504),
  `_pendiente`=`req>0` (~L512), `page = agg[:limit]`.
