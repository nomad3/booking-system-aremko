# Brief — Anti-duplicado + orden de cadencia (outbox masajes) y normalización periódica de ciudades

> **Handoff para el agente que trabaja en Django (booking-system-aremko).**
> **Solicitado por:** Jorge · **Desde:** sesión aremko-cli · **Fecha:** 2026-06-10
> **Lado que implementa:** Django (este repo). aremko-cli solo consume la API; no cambia.

---

## ⚠️ Aviso: esto puede estar PARCIALMENTE DUPLICADO

Es muy probable que **parte de esta solicitud ya te la hayamos pasado en una sesión anterior que se interrumpió por un corte de luz** y quedó a medias. Antes de implementar:

1. **Revisa si ya hiciste algo de esto** (busca commits/ramas recientes con `anti`, `dedup`, `cooldown`, `cadencia`, `orden`, o cambios en `SeguimientoBienestarMasaje` / `masaje_seguimiento_service`).
2. Si **ya está implementado total o parcialmente**, no rehagas: **confírmanos el estado** (qué quedó hecho, qué falta) y seguimos desde ahí.
3. Si **no hay rastro**, implementa desde cero según este brief.

No asumas que partes de cero ni que ya está todo; **verifica primero**.

---

## 1. Contexto

La bandeja **"Conexión-Masajes"** (en aremko-cli) lista los `SeguimientoBienestarMasaje` con `estado='pendiente'` y permite a Debora/Angélica/Jorge revisarlos y enviarlos **uno por uno**. El reparto es el de siempre: **Django = fuente de verdad + motor de envío**; aremko-cli = UI.

**El problema:** un mismo cliente puede tener **varios correos pendientes a la vez** (p. ej. `gracias_visita` + `resumen_bienestar`, o seguimientos de visitas distintas). Hoy:

- El outbox **no aplica ninguna regla** de no-saturación ni de orden: solo expone los `pendiente`.
- aremko-cli ya muestra un **aviso visual** *"⚠️ N correos para este cliente"*, pero es **solo frontend** — nada impide que el operador mande dos correos seguidos a la misma persona, ni garantiza el orden correcto.

Queremos que **la garantía la ponga Django**, no la disciplina del operador.

**Prior art a reutilizar:** la *regla anti-saturación de 30 días* que ya existe para el WhatsApp outbound (`Cliente.ultimo_contacto_outbound` + `Cliente.proximo_contacto_no_antes_de`, ver `ventas/models.py:801-813`). El mecanismo de "última fecha de contacto + no-antes-de" es el patrón que pedimos replicar (adaptado a email de masajes), no inventar uno nuevo.

---

## 2. Lo que pedimos

### R1 — Anti-duplicado / no-saturación por cliente

**Objetivo:** no enviar dos correos al **mismo cliente** en una ventana demasiado corta.

- Al **enviar** un seguimiento (`POST /api/masaje/outbox/<id>/send/`), si ese cliente **ya recibió** otro correo de masajes hace **menos de N horas/días**, el envío debe **bloquearse o avisar**, no salir en silencio.
- Sugerencia de contrato: devolver un **`409`** (o un `422` específico) con un cuerpo claro, p. ej.
  `{ "ok": false, "motivo": "anti_saturacion", "detalle": "Ya se le envió un correo hace 3 h; espera hasta DD/MM HH:MM", "ultimo_envio": "2026-06-10T13:00:00-04:00" }`
  para que aremko-cli lo muestre como un mensaje claro en vez de un error genérico.
- **Que la lista (`GET /api/masaje/outbox/`) lo refleje:** agregar a cada item un flag tipo
  `"bloqueado_por_saturacion": true/false` (+ `"desbloquea_en": "<ISO>"`), así aremko-cli puede **deshabilitar el botón Enviar** y mostrar el porqué antes de que el operador intente.

**Decisiones a confirmar con Jorge (no las cierres sin preguntar):**
- **Ventana N**: ¿24 h? ¿48 h? (la de WhatsApp es de 30 días, pero email post-masaje es otro ritmo).
- **¿Aplica a los transaccionales?** `gracias_visita` y `resumen_bienestar` son transaccionales y pueden ir legítimamente cerca uno de otro. Propuesta: **la ventana anti-saturación aplica solo entre comerciales** (`seguimiento_7d`/`recomendacion_30d`/`reactivacion_60d`/`reactivacion_90d`), y los transaccionales quedan exentos (pero ver R2 para su orden). Confirmar.
- **¿Override manual?** ¿El operador puede "enviar igual" pese al bloqueo (con confirmación), o el bloqueo es duro?

### R2 — Orden de la cadencia: **gracias antes que resumen**

**Objetivo:** que al mismo cliente le llegue primero el **`gracias_visita`** y después el **`resumen_bienestar`**, nunca al revés.

- **Estado actual:** los offsets son `resumen_bienestar` = inmediato y `gracias_visita` = +24 h (ver §6.b del brief de la bandeja). Es decir, **hoy el orden sale al revés** del deseado: el resumen tiende a salir antes que el gracias.
- Pedimos **garantizar el orden gracias → resumen** para un mismo cliente. Mecanismo a elección del agente Django (cualquiera de estos, lo que sea más limpio):
  - **(a)** Ajustar los offsets de programación para que `gracias_visita` quede antes que `resumen_bienestar`; **o**
  - **(b)** Regla en el `send`: no permitir enviar `resumen_bienestar` si aún hay un `gracias_visita` `pendiente` para el mismo cliente/visita (bloquear con mensaje, igual que R1); **o**
  - **(c)** Reordenar la lista que entrega el endpoint para que el `gracias_visita` aparezca primero y el `resumen_bienestar` quede bloqueado hasta que el gracias se haya enviado.
- **Preferencia de Jorge:** que el **orden esté garantizado del lado Django** y no dependa de que el operador elija bien. Confirmar con él si prefiere (a) reprogramar offsets vs (b/c) bloqueo en el envío.

---

## 3. Normalización periódica de ciudades (relacionado, lado Django)

**Contexto:** el comando `manage.py normalizar_ciudades_clientes` ya existe y ya se corrió una vez (dejó el outbox 100% `sur`). Pero los **clientes nuevos** que llenan ficha entran como **`sin_clasificar`** hasta que alguien lo corre a mano.

**Pedido:** que la normalización se ejecute **periódicamente y sola**, para que la bandeja no vuelva a llenarse de `sin_clasificar`.

- **Restricción de infra (importante):** en Render las **auto-migrations están deshabilitadas** y la app corre con **1 worker Gunicorn**; el patrón conocido para tareas periódicas es **cron-subprocess** (ver AR-030). Usa ese patrón o un **Render Cron Job** que invoque `manage.py normalizar_ciudades_clientes`, lo que sea más robusto.
- **Cadencia sugerida:** diaria o cada pocas horas (volumen bajo; el comando es idempotente).
- **Idempotencia:** confirma que el comando no pisa las clasificaciones **manuales** (las que tienen `ciudad_normalizada_manual=True` no se deben sobreescribir).

---

## 4. Lo que NO cambia (para que no rompamos el contrato con aremko-cli)

- **No cambies** los nombres ni la forma de los campos existentes del item del outbox; **solo agrega** flags nuevos (`bloqueado_por_saturacion`, `desbloquea_en`, motivo de error). El contrato de `docs/BRIEF_BANDEJA_MASAJES_AREMKO_CLI.md` debe seguir válido.
- **No** muevas el motor de envío ni el branding a aremko-cli: sigue siendo de Django.
- Mantén los códigos HTTP ya pactados (`200/400/401/404/409/422`); si agregas un motivo nuevo, hazlo **dentro** del body, no con un código distinto.

---

## 5. Entregable esperado de tu lado

1. R1 + R2 implementados (o el reporte de "ya estaba hecho / esto faltaba").
2. Normalización periódica andando en Render.
3. **Una nota corta de vuelta** (un `docs/RESPUESTA_*.md`, como el de la bandeja) con: qué quedó, los **valores finales** elegidos (ventana N, qué tipos aplican, mecanismo de orden), y los **campos nuevos exactos** del JSON para que aremko-cli ajuste la UI (deshabilitar botón, mostrar motivo).

---

## 6. Referencias (este repo)

- Modelo: `SeguimientoBienestarMasaje` — `ventas/models.py:7746`
- Prior art anti-saturación: `Cliente.ultimo_contacto_outbound` / `proximo_contacto_no_antes_de` — `ventas/models.py:801-813`
- API outbox: `ventas/views/masaje_outbox_api_views.py` (endpoints `/api/masaje/outbox/...`)
- Render del email: `ventas/services/masaje_seguimiento_service.py`
- Comando de geo: `manage.py normalizar_ciudades_clientes`
- Contrato vigente con aremko-cli: `docs/BRIEF_BANDEJA_MASAJES_AREMKO_CLI.md` y `docs/RESPUESTA_OUTBOX_GEO_AREMKO_CLI.md`
