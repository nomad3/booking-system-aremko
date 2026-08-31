# BRIEF H-110 — Cerrar con auth el backend Go (endpoints del inbox abiertos a internet)

**Para:** agente aremko-cli · **De:** agente Django · **Fecha:** 2026-08-31 · **Prioridad: ALTA (seguridad)**

## El hallazgo

Durante el diagnóstico del bug de la bandeja (el «+» comido — ya resuelto en Django, commit `9a3329ed`), se comprobó que el backend Go (`aremko-cli-backend` en Render, `srv-d810ffjbc2fs738j1rc0`) responde **sin ninguna credencial** a internet:

```
GET https://aremko-cli-backend.onrender.com/api/v1/inbox/conversations        → 200, lista completa
GET https://aremko-cli-backend.onrender.com/api/v1/inbox/conversation?...     → 200, hilo completo
GET https://aremko-cli-backend.onrender.com/api/v1/whatsapp/conversation?...  → 200, hilo completo
```

Cualquiera con la URL lee **conversaciones reales de clientes** (nombres, teléfonos, mensajes). Probado con `curl` pelado el 2026-08-31.

## El encargo

1. **Auth en las rutas `/api/v1/*`** del server Go (`backend/internal/api/server.go`): un API key propio en header (p. ej. `X-CLI-Key`), validado por middleware.
2. **Excepciones que deben quedar SIN auth de app**: `/health` (lo usa Render) y los webhooks de Meta (`/instagram/webhook`, `/messenger/webhook`) — esos ya validan firma HMAC propia y Meta no puede mandar headers custom.
3. **La llave**: env var en Render (backend) y en el frontend de Vercel (`…cli-frontend.vercel.app`). ⚠️ Memoria previa: cuidado con el proyecto duplicado de Vercel con env distinta (ya mordió una vez).
4. **De pasada (prolijidad, no urgencia)**: redeploy del frontend desde main — el build desplegado manda el `+` del teléfono sin codificar; Django ya es tolerante, pero conviene alinear.

## Verificación al cerrar

- `curl` sin credencial → 401 en `/api/v1/inbox/*`.
- Con credencial → 200.
- Los webhooks de Meta siguen recibiendo (mandar un DM de prueba a Instagram).
- La bandeja del celular de Jorge sigue funcionando (ver hilo + responder).

## Contexto Django (nada que hacer de este lado)

La tolerancia al «+» quedó en `inbox_omnicanal/views.py` con pruebas (`inbox_omnicanal/tests/test_hilo_mas_comido.py`). Si el Go agrega auth, **no cambia el contrato** con Django (X-API-Key LUNA_API_KEY sigue igual hacia atrás).
