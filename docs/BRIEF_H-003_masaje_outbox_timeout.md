# BRIEF H-003 — `/api/masaje/outbox/` tarda >10s → timeout en Conexión-Masajes

- **Solicita:** agente aremko-cli
- **Implementa:** agente Django (`booking-system-aremko`)
- **Fecha:** 2026-06-13
- **Estado:** SOLICITADO

## Síntoma (visto por Jorge en prod, 2026-06-13)

La página **Conexión-Masajes** de aremko-cli muestra, de forma **persistente** (no se va al Refrescar):

```
error en GET /api/masaje/outbox/?incluir_programados=1&limit=200:
Get "https://www.aremko.cl/api/masaje/outbox/?incluir_programados=1&limit=200":
context deadline exceeded (Client.Timeout exceeded while awaiting headers)
```

## Diagnóstico hecho desde aremko-cli

- El cliente Go que proxea a Django tiene **timeout de 10s** (`backend/internal/bookings/client.go` → `http.Client{Timeout: 10 * time.Second}`). El error = Django **no respondió en <10s**.
- `GET /api/masaje/outbox/` **sin** `X-API-Key` responde **401 en 0.24s** → el portero (`_check_luna_key`) es rápido. Lo lento es la **vista autenticada** (`ventas/views/masaje_outbox_api_views.py:182 outbox_list`).
- `https://www.aremko.cl/` (home) responde 200 en ~1s → Django en general está vivo; es **esta vista** la que se pasa de 10s.
- Infra (de `CLAUDE.md`): **Gunicorn 1 worker, timeout 120s**; **DB timeout 10s**. Es decir, Django podría estar tardando entre 10 y 120s en armar la respuesta, o pegando contra el timeout de DB de 10s.

## Hipótesis (ordenadas por probabilidad)

1. **Render de previews inline (lo más probable):** `outbox_list` arma `para_enviar` con
   `_serialize(s, include_preview=True, ...)` **por cada** seguimiento vencido (línea 204).
   Si hay **muchos pendientes acumulados** (no se han enviado justamente porque la bandeja
   falla → bola de nieve), renderizar N previews de email inline es O(N) y caro. Nota: el
   frontend muestra "0 / 0" pero eso es el **estado vacío por defecto tras el fetch fallido**,
   NO significa que haya 0 en la BD. Hay que mirar el conteo real.
2. **Falta de índice:** `SeguimientoBienestarMasaje.objects.filter(estado='pendiente')` +
   `fecha_programada__lte/gt` (líneas 198-209). Si la tabla creció y `estado` /
   `fecha_programada` no están indexados → full scan que pega contra el timeout de DB (10s).
3. **Contención del único worker:** el reporte diario (~9:15) u otra request larga ocupando
   el worker. Menos probable porque persiste entre refrescos separados por minutos.

## Pedido al agente Django

1. **Medir** la duración real de `outbox_list` y **cuántos** `estado='pendiente'` hay
   (vencidos vs futuros) en prod. Confirmar cuál hipótesis es.
2. Si es (1): **no renderizar el preview en la lista** — devolver solo metadatos (asunto,
   destinatario, fecha, bloqueo) y dejar el HTML para `/preview/` (que ya existe y se pide
   por item). O cachear/limitar el render.
3. Si es (2): agregar índice(s) a `SeguimientoBienestarMasaje(estado, fecha_programada)`
   (migración; recordar `migrate` manual en Render — auto-migrations off).
4. **Aceptación:** `GET /api/masaje/outbox/?incluir_programados=1&limit=200` responde
   **<2-3s** consistente, y Conexión-Masajes en aremko-cli carga sin timeout.

## Coordinación con aremko-cli

- Parche opcional del lado aremko-cli: subir el timeout del cliente Go de 10s → ~25s
  (`backend/internal/bookings/client.go`). Es **band-aid**: tolera la lentitud pero no la
  arregla. Preferible corregir en origen (Django). Si Django queda <3s, el parche no hace falta.
- No bloquea operación hoy (no había envíos urgentes), pero la página muestra el error.

## Punteros

- Vista: `ventas/views/masaje_outbox_api_views.py` → `outbox_list` (L182), `_serialize`, `include_preview`.
- Bloqueos/anti-saturación: `ventas/services/masaje_seguimiento_service.py` → `calcular_bloqueos` (L120, "evita N+1").
- URL: `aremko_project/urls.py:59`.
