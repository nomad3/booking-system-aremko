# BRIEF H-111 — Correo semanal: Datamatic genera, Aremko envía

**Estado:** EN PROGRESO (Django) desde 2026-09-14. **Contrato único** (acordado con Jorge
el 12-09 y confirmado el 14-09 tras la revisión cruzada con el agente de Datamatic).

## Decisiones de Jorge (12-09-2026)

1. **No se dispara sola.** La campaña nace en **Borrador**. Jorge o Deborah la abren en
   *Campañas de Email* del admin de Aremko, la revisan con *Vista previa*, cambian el
   estado a **«Lista para envío»** y guardan. El cron la manda dentro de los 5 minutos
   siguientes, de 08:00 a 21:00.
2. **Máximo 1.000 destinatarios por lote.**
3. **El lote lo arma Aremko, no Datamatic.** Van todos los clientes con correo, en fila,
   por lotes. Datamatic **no manda segmento** (si manda uno distinto de `todos`, el
   endpoint responde 400).
4. **La baja tiene que quedar clara.** El motor de Aremko agrega el pie con una frase
   completa y el enlace de baja, más el botón de baja de Gmail/Yahoo (List-Unsubscribe
   one-click). La lista negra se revisa correo por correo al enviar.

## Contrato del endpoint (lado Django, deploy 2)

```
POST https://www.aremko.cl/marketing/api/campana-semanal/
X-API-KEY: <AUTOMATION_API_KEY>      ← la MISMA llave que Datamatic ya usa para
                                        /marketing/api/catalogo/ y /marketing/api/resenas/
Content-Type: application/json
```

```json
{
  "asunto":      "Hola {nombre_cliente}, esta semana en Aremko…",   // obligatorio, ≤ 300 caracteres
  "cuerpo_html": "<table role=\"presentation\" …>…</table>",        // obligatorio, ver reglas abajo
  "nombre":      "Correo semanal 2026-09-18",                         // opcional; default «Correo semanal <fecha de hoy>»
  "lotes":       1,                                                    // opcional, 1..6; cada lote ≤ 1.000
  "origen":      "datamatic"                                          // opcional, se guarda en la descripción
}
```

**Reglas del `cuerpo_html`:** fragmento (sin `<html>`/`<body>`), 600 px, estilos en línea,
fotos con `f_jpg` explícito, **≤ 100 KB**, sin `<script>`, **sin pie de baja** (lo pone el
motor; dos pies dejarían uno mentiroso). `{nombre_cliente}` viaja **literal** en asunto y
cuerpo: Aremko lo reemplaza por el primer nombre con un `replace` simple al crear los
destinatarios.

**Respuestas**

| Código | Cuándo | Cuerpo |
|---|---|---|
| 201 | Campaña(s) creada(s) | `{"ok": true, "campanas": [{"id": 123, "nombre": "Correo semanal 2026-09-18", "destinatarios": 1000, "estado": "draft", "revisar_en": "https://www.aremko.cl/admin/ventas/emailcampaign/123/change/"}], "universo": 5282, "sin_lote": 4282}` |
| 200 | Misma llamada repetida (mismo `nombre`) | Igual que 201 pero con `"repetida": true`. **No duplica.** |
| 400 | Falta asunto o cuerpo · cuerpo > 100 KB · `<script>` · `segmento` ≠ `todos` · `lotes` fuera de 1..6 · nadie elegible | `{"ok": false, "error": "…"}` |
| 401 | Sin `X-API-KEY` o llave incorrecta | `{"error": "X-API-KEY inválida o ausente"}` |

Con `lotes` > 1 se crean N campañas en Borrador, nombradas `<nombre> · lote i/N`, con
destinatarios disjuntos. Cada una se aprueba por separado.

## Cómo arma Aremko cada lote (fijo, sin elegir nada a mano)

1. Entran los clientes cuyo correo tiene `@`. Un correo repetido entre varios clientes entra
   una sola vez (en minúsculas).
2. Salen: lista negra activa (`EmailBlacklist`), bajas del newsletter, y correos que ya
   están **esperando en otra campaña** (draft/ready/sending con destinatario pendiente).
3. Salen los que **recibieron un correo de campaña en los últimos 28 días**.
4. Los que quedan se ordenan por **fecha de última compra, la más reciente primero**; los
   que nunca compraron van al final.
5. El lote toma los primeros 1.000 de esa fila.

Datos reales al 12-09-2026: 5.343 correos válidos, 114 excluidos → **5.282 elegibles = 6
lotes**. Un correo semanal cubre la base en 6 semanas; cada cliente recibe uno cada mes y
medio. Si un día se quiere que todos reciban el mismo correo, `lotes: 6`.

## Qué hace la campaña creada

`EmailCampaign` en `draft`, `ai_variation_enabled=False` (**siempre**, aunque lo pidan),
`schedule_config = {start_time: "08:00", end_time: "21:00", batch_size: 50,
interval_minutes: 5, ai_enabled: false}`, `EmailRecipient` por destinatario con asunto y
cuerpo ya personalizados. Envío: el cron existente `/ventas/cron/enviar-campanas-email/`
(cron-job.org, cada 5 min) manda **un lote de 50 por pasada** → 1.000 correos en ≈ 1 h 40.

## Plan de deploys (Django)

- **Deploy 1** (motor): frase de baja completa en el pie + cron en modo «un lote por
  pasada» (`--single-batch`). Verificación: línea nueva en el log del cron + correo de prueba
  a la casilla de Jorge.
- **Deploy 2**: el endpoint de arriba + pruebas (401 sin llave; IA apagada aunque la pidan;
  tope 1.000; cada exclusión; orden por última compra; idempotencia por nombre).
- Al terminar: `RESPUESTA_H-111_*.md` + aviso al agente de Datamatic para que adapte su lado
  (deja de mandar `segmento`; su pantalla dice «Lo arma Aremko: los próximos 1.000 de la
  fila»; corre `instalar_aremko` del correo recién entonces).

## Lado Datamatic (ya construido, commit `0d0e7b0` del 11-09)

`apps/publicaciones/correo.py` + `publicaciones/correo_semanal.html`: el HTML lo arma el
módulo (fragmento `<table>` 600 px, `f_jpg`, preheader oculto, `{nombre_cliente}` literal,
sin pie). Pendiente de su lado: llamar a este endpoint con `asunto` + `cuerpo_html`, mostrar
`revisar_en` como enlace «Revisar y aprobar en Aremko», y no enviar `segmento` para Aremko.
