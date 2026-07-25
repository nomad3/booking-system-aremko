# CONTRATO H-070 · API del Catálogo de Clips (Fase A)

> **Autor:** Django (`booking-system-aremko`) · **Consumidores:** aremko-cli (front de
> ingesta + explorador, Fase B) y el script LOCAL de semilla (push local→nube).
> **Auth:** header `X-API-KEY == AUTOMATION_API_KEY` en TODOS los endpoints.
> Base prod: `https://www.aremko.cl`.

## Flujo

```
[operador sube foto] → POST /ingesta/  (Cloudinary optimizada + draft IA, NO persiste)
        ↓ operador confirma/corrige el draft en el front
[guardar]            → POST /          (upsert por `archivo` → Clip persistido)
[explorar]           → GET  /          (filtros para el front / auto-pick futuro)
[curar]              → PATCH /<id>/    (editar taxonomía / estado / keeper)
```

## 1) `POST /marketing/api/catalogo/ingesta/`

Multipart, campo **`imagen`** (`.jpg .jpeg .png .webp`, máx 16 MB — NO el master).
Sube a Cloudinary **solo la versión optimizada** (incoming `w_1440,c_limit,q_auto`; se
sirve con `f_auto,q_auto`) y corre el etiquetado IA. **No persiste nada.**

**200:**
```json
{
  "archivo": "IMG_2795.jpg",
  "cloud_url": "https://res.cloudinary.com/dtuncr1pi/image/upload/f_auto,q_auto/catalogo_clips/ab12cd.jpg",
  "width": 1440, "height": 1080,
  "persistido": false,
  "draft": {
    "area": "tina", "nombre_comercial": "Villarrica-Llaima",
    "momento": "atardecer", "estacion": "indistinto",
    "vapor": "sí", "decoracion": "con",
    "personas": false, "permiso": "libre",
    "calidad": "alta", "keeper": true,
    "descripcion": "Tina redonda humeante junto al río al atardecer",
    "orientacion": "horizontal", "estado": "ok",
    "etiquetas": ["tina", "vapor", "atardecer"],
    "apto_para": ["hero", "instagram_feed"]
  }
}
```
Errores: `400` (falta archivo / formato / >16MB) · `401` · `502` (Cloudinary).
Si la IA duda o falla: draft con defaults conservadores y `estado="revisar"` (la ingesta
no se cae por el etiquetado). Reglas duras del saneo: `personas=true` fuerza
`permiso="revisar_derechos"` y `keeper=false`.

## 2) `POST /marketing/api/catalogo/` — guardar confirmado (upsert)

JSON. Obligatorios: **`archivo`**, **`cloud_url`**, **`area`**. El resto opcional
(defaults del modelo). **Idempotente: upsert por `archivo`** — la semilla puede correr
N veces sin duplicar (si el `archivo` existe, actualiza).

```json
{
  "archivo": "IMG_2795.jpg",
  "cloud_url": "https://res.cloudinary.com/.../catalogo_clips/ab12cd.jpg",
  "tipo": "foto",
  "area": "tina", "nombre_comercial": "Llaima",
  "momento": "atardecer", "estacion": "indistinto",
  "vapor": "sí", "decoracion": "con",
  "personas": false, "permiso": "libre",
  "calidad": "alta", "keeper": true,
  "descripcion": "…", "orientacion": "horizontal",
  "estado": "ok", "fuente": "disco", "nota": "", "origen": "",
  "etiquetas": ["tina", "vapor"], "apto_para": ["hero"],
  "atributos": {"hidromasaje": true}
}
```
**201** (creado) / **200** (actualizado): `{"clip": {…shape completo…}, "creado": true|false}`.
Errores: `400` con `{"error": "<campo> inválido: …"}` · `401`.

Valores permitidos:
- `tipo`: `foto|video` (Fase A opera foto) · `area`: `tina|masaje|cabaña|entorno|detalle|aereo|recepcion|entorno_region`
- `momento`: `dia|atardecer|noche|indistinto` · `estacion`: `invierno|verano|indistinto`
- `vapor`: `no|sí|sí (IA)` (la IA solo propone `no|sí`; `sí (IA)` lo marca el operador)
- `decoracion`: `con|sin|""` · `permiso`: `libre|revisar_derechos`
- `calidad`: `alta|media` · `estado`: `ok|revisar|descartado`
- `etiquetas`/`apto_para`: listas de strings · `atributos`: objeto libre (extras por
  vertical; en Aremko p.ej. `hidromasaje`).

## 3) `GET /marketing/api/catalogo/` — explorar

Query params (todos opcionales, se combinan):
`area, nombre_comercial (icontains), keeper (true/false), vapor, momento, estado, tipo,
apto_para (un valor, membership), q (busca en archivo/nombre/descripcion/nota),
limit (default 100, máx 500), offset`.

**200:**
```json
{"total": 89, "limit": 100, "offset": 0, "clips": [ {…shape completo…}, … ]}
```

### Shape completo del clip (respuesta de POST/GET/PATCH)
```json
{
  "id": 1, "archivo": "IMG_2795.jpg", "cloud_url": "https://…",
  "tipo": "foto", "area": "tina", "nombre_comercial": "Llaima",
  "momento": "atardecer", "estacion": "indistinto", "vapor": "sí",
  "decoracion": "con", "personas": false, "permiso": "libre",
  "calidad": "alta", "keeper": true, "descripcion": "…",
  "orientacion": "horizontal", "estado": "ok", "fuente": "disco",
  "nota": "", "origen": "", "etiquetas": [], "apto_para": [],
  "atributos": {}, "creado": "2026-07-24T…", "actualizado": "2026-07-24T…"
}
```

## 4) `PATCH /marketing/api/catalogo/<id>/` — curar

JSON parcial: cualquier subconjunto de los campos del POST **excepto `archivo`**
(la clave de upsert no se edita; si viene, se ignora). Mismas validaciones.
**200:** `{"clip": {…}}` · `404` si el id no existe · `400`/`401`.

## Notas para la semilla (script LOCAL, lado aremko-cli/Jorge)
- Por cada keeper del `catalogo.json` local: subir la imagen vía `POST /ingesta/`
  (obtiene `cloud_url` — puedes ignorar el draft si ya traes la taxonomía curada) y
  luego `POST /` con la taxonomía del JSON + ese `cloud_url`.
- Alternativa más barata en tokens: subir a Cloudinary directo desde el script (mismo
  preset `w_1440,c_limit,q_auto`) y solo hacer `POST /` con el `cloud_url` resultante —
  la ingesta con IA es para fotos NUEVAS sin taxonomía.
- Re-correr el script es seguro (upsert por `archivo`).

## Fuera de alcance Fase A
Render/composición (Fase B, navegador) · video (local) · multi-tenant (el modelo quedó
port-friendly: universales explícitos + `atributos` JSON; FK `empresa` documentado, no creado).
