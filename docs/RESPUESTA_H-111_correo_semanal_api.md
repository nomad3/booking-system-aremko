# RESPUESTA H-111 — Correo semanal: el endpoint está en producción (lado Django)

**Fecha:** 2026-09-14 · **Estado:** IMPLEMENTADO (Django) — esperando que Datamatic
consuma el endpoint.

## Qué quedó desplegado (tres deploys, en este orden)

1. **Deploy 1 (`10d63ac6`)** — pie de baja con frase completa («Si no quieres recibir más
   correos de Aremko, date de baja aquí con un clic») + cron de campañas en modo
   **un lote por pasada** (`--single-batch`).
2. **Deploy 1b (`dc5cdbac`)** — las campañas salen desde **«Aremko Spa Boutique
   <comunicaciones@aremko.cl>»** con **Reply-To ventas@aremko.cl**. Motivo: con el From de
   Render (`aremkospa@gmail.com`) Gmail acepta el boletín y lo descarta en silencio; SendGrid
   igual dice «delivered». Verificado con correos reales a la casilla de Jorge.
3. **Deploy 2** — `POST /marketing/api/campana-semanal/` (este documento).

## El contrato, tal cual quedó

```
POST https://www.aremko.cl/marketing/api/campana-semanal/
X-API-KEY: <AUTOMATION_API_KEY>          (la misma llave que /marketing/api/catalogo/)
Content-Type: application/json

{"asunto": "Hola {nombre_cliente}, …",         obligatorio, ≤ 300 caracteres
 "cuerpo_html": "<table>…</table>",             obligatorio, fragmento, ≤ 100 KB, sin <script>, SIN pie de baja
 "nombre": "Correo semanal 2026-09-18",         opcional; default «Correo semanal <hoy>»; idempotente
 "lotes": 1,                                    opcional, 1..6; cada lote ≤ 1.000
 "origen": "datamatic"}                         opcional; queda en la descripción
```

| Código | Cuándo | Respuesta |
|---|---|---|
| 201 | creó | `{"ok": true, "repetida": false, "campanas": [{"id", "nombre", "destinatarios", "estado": "draft", "revisar_en"}], "universo": N, "sin_lote": M}` |
| 200 | mismo `nombre` otra vez | igual, con `"repetida": true` y las campañas ya existentes; **no duplica** |
| 400 | falta asunto/cuerpo · > 100 KB · `<script>` · `segmento` ≠ `todos` · `lotes` fuera de 1..6 · nadie elegible · JSON inválido | `{"ok": false, "error": "…"}` |
| 401 | sin llave o llave mala | `{"error": "X-API-KEY inválida o ausente"}` |
| 405 | GET | — |

`revisar_en` es la página de la campaña en el admin de Aremko: sirve para mostrar en
Datamatic un enlace «Revisar y aprobar en Aremko».

**Lo que hace Aremko con eso:** arma la fila (todos los clientes con correo válido, sin
repetidos; fuera lista negra, bajas del newsletter, quien ya espera en otra campaña y quien
recibió un correo en los últimos 28 días; orden última compra más reciente primero, sin
compra al final), toma los primeros 1.000 por lote, y crea la campaña en **Borrador** con
`{nombre_cliente}` ya reemplazado por el primer nombre, IA apagada y envío de 50 cada 5
minutos entre 08:00 y 21:00. **Nada sale hasta que Jorge o Deborah la pasen a «Lista para
envío»** en Campañas de Email.

## Lo que falta del lado Datamatic

- Llamar al endpoint con `asunto` + `cuerpo_html` (+ `nombre` con la semana, para que la
  repetición no duplique). No mandar `segmento` (o mandar `"todos"`).
- Mostrar `revisar_en` como enlace y el conteo de `destinatarios`.
- Pantalla: «Lo arma Aremko: los próximos 1.000 de la fila».
- Recién entonces correr `instalar_aremko` del correo del viernes.

## Pruebas

`ventas/tests_api_campana_semanal.py` (31) + `ventas/tests_correo_baja_y_cron.py` (10):
llave, borrador + IA off, reemplazo del nombre, tope 1.000 y lotes disjuntos, cada
exclusión, el orden de la fila, idempotencia, cada 400, el pie, el cron y el remitente.
Verificadas rompiendo cada regla.
