# Contrato H-065 / H-066-F2 — Video en `publicacion_material` + revisión por clip (v1)

**Autor:** agente Django · 2026-07-19 · Estado: v1 vigente
**Productor:** front aremko-cli (Angélica sube el archivo) → proxy Go `PublicacionMaterial` (body 110 MB / timeout 180s, ya deployado por aremko-cli)
**Consumidores:** Django (`publicacion_material` sube a Cloudinary + `revision_service` revisa por fotogramas), front aremko-cli (render del material y del veredicto), futuro F3 (unión de clips) y port M17.

Este documento es la fuente de verdad del contrato de subida de VIDEO y del shape
de `material_meta` para video. Si cambia, se anota acá; los consumidores toleran
campos desconocidos y no asumen campos no listados.

## Flujo

1. Angélica genera el micro-video de una toma (IA image-to-video con el `prompt_video_ia`
   del segmento) o exporta el reel completo.
2. El front lo sube: `POST /api/aremko-cli/publicaciones/<id>/material/` (multipart,
   campo `files`, header `X-API-KEY`), con `segmento=<indice>` si es el clip de UNA toma
   (1..3) o sin `segmento` si es el reel entero.
3. Django valida (extensión, tope, `tipo='reel'`), sube a Cloudinary con
   `resource_type=video` (chunked) y captura la metadata de la respuesta del upload
   (duración, dimensiones) → item de `material_meta` con `tipo: "video"`.
4. Responde de inmediato con la publicación serializada (`revision_veredicto='revisando'`
   en el nivel que corresponda) y dispara la revisión IA en background — igual que fotos.
5. La revisión NO descarga el video: deriva fotogramas por transformación URL de
   Cloudinary (`so_<segundos>` + `w_720,q_auto` + extensión `.jpg`) y los pasa al modelo
   de visión con un prompt específico de reels (marca de agua cruzada y de herramienta IA
   = crítico; fidelidad a la toma y su prompt; artefactos de IA; formato 9:16). El
   veredicto llega por polling de `publicacion_detalle`, como siempre.

## Reglas de subida (v1)

| Regla | Valor |
|---|---|
| Extensiones video | `.mp4`, `.mov` |
| Dónde se acepta | SOLO publicaciones `tipo='reel'` (Instagram y TikTok). Otras piezas → 400. |
| Tope por archivo | **100 MB** (bajo el body de 110 MB del proxy Go). **Recomendado <40 MB** — un clip H.264 real pesa 5-20 MB; comprimir antes si viene de iPhone 4K. |
| Con `segmento=<indice>` | El video es el micro-clip de ESA toma; material y veredicto van al segmento. |
| Sin `segmento` | Es el reel completo; material y veredicto a nivel publicación. |
| Mezcla en una request | Permitida (fotos y videos en `files`); cada archivo por su rama. |
| Versiones | Se APPENDEA a `material_urls`/`material_meta` (historial); la revisión evalúa el ÚLTIMO video subido (la versión vigente). |

## Item de `material_meta` para video (v1)

```json
{
  "url": "https://res.cloudinary.com/dtuncr1pi/video/upload/v.../publicaciones/2026-07-20/ab12.mp4",
  "tipo": "video",
  "width": 1080,
  "height": 1920,
  "ratio": "9:16",
  "orientacion": "vertical",
  "duration": 8.3,
  "bytes": 24500000,
  "format": "mp4"
}
```

### Semántica de campos

| Campo | Notas |
|---|---|
| `url` | `secure_url` de Cloudinary (`/video/upload/`). Siempre presente. |
| `tipo` | `"video"` — el discriminador. **Las fotos NO llevan `tipo`** (retrocompatible: item sin `tipo` = imagen). |
| `width`/`height`/`ratio`/`orientacion` | Medidos por Cloudinary al subir (mismo `_ratio_label` que fotos). Pueden faltar si la metadata falló — tolerar ausencia. |
| `duration` | Segundos (float, 1 decimal). Puede faltar. |
| `bytes` / `format` | Peso real y formato (`mp4`/`mov`). Pueden faltar. |

## Reglas para consumidores

- **Front aremko-cli:** item con `tipo == "video"` → render `<video controls playsinline>`
  con la `url`; **poster/thumbnail** = la misma `url` con `/upload/` → `/upload/so_0,w_720,q_auto/`
  y extensión `.jpg` (así se deriva cualquier fotograma: `so_<segundos>`). El estado
  `revisando` → veredicto por polling, sin cambios respecto a fotos.
- **Django/revisión:** el último item de material que sea video define la rama; el
  contexto del clip sale del segmento (`texto`, `prompt_video_ia`) + `copy_json` del reel.
- **Errores 400 con mensaje claro:** extensión no soportada, video en pieza no-reel,
  tope excedido. 502 si Cloudinary falla. El front puede mostrar el `error` tal cual.

## Pendiente por lado

- **aremko-cli:** botón "Subir video" en el clip (los segmentos del reel ya se renderizan
  desde H-066 F1) y en la pieza reel a nivel publicación; render `<video>` + poster.
  El proxy ya está listo — solo front.
- **Django:** nada — deployado con este contrato (commit de H-065/H-066 F2).
- **F3 (siguiente):** unir los 3 clips aprobados (concatenación Cloudinary, sin ffmpeg).
