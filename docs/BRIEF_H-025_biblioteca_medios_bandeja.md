# BRIEF H-025 — Biblioteca de medios para la bandeja (fotos/videos del catálogo)

**Pedido de Jorge (2026-06-18):** cuando un cliente pide "foto de la cabaña Torre"
o "foto de la tina Hornopiren", hoy Jorge tiene que buscar en su celular y pierde
tiempo. Queremos que el botón de adjuntar en la bandeja abra una **galería con las
fotos que YA están en la web** (tinas, cabañas, masajes), elija una miniatura y se
envíe por el canal de la conversación.

**Decisión de Jorge:** la biblioteca se alimenta del **catálogo del sitio** (auto-sync,
cero mantención) e incluye **fotos + videos**.

## Lo que pide (lado Django)

Nuevo endpoint read-only **`GET /api/inbox/media-library`** (auth `X-API-Key: LUNA_API_KEY`,
igual que los demás `/api/inbox/*`).

Devuelve los **Servicios publicados** agrupados por `tipo_servicio`, con sus imágenes
y video. Solo `tina`, `cabana`, `masaje` (omitir `otro`). Filtro: `publicado_web=True`
(y `activo=True` si tiene sentido). Usar las URLs absolutas de Cloudinary/GCS
(`imagen.url`, etc.), saltando las vacías.

Shape sugerido:
```json
{
  "grupos": [
    {
      "tipo": "tina",
      "label": "Tinas",
      "items": [
        {
          "id": 12,
          "nombre": "Tina Hornopiren",
          "fotos": ["https://.../imagen.jpg", "https://.../imagen_2.jpg"],
          "video": "https://.../video.mp4"   // o null (video subido o video_url)
        }
      ]
    },
    { "tipo": "cabana",  "label": "Cabañas", "items": [ ... ] },
    { "tipo": "masaje",  "label": "Masajes", "items": [ ... ] }
  ]
}
```
Notas:
- `fotos`: lista de `imagen`, `imagen_2`, `imagen_3` que NO estén vacías (`.url`).
- `video`: el `video` subido (`.url`) si existe; si no, `video_url`; si ninguno, `null`.
- Orden: por `tipo` (tina, cabana, masaje) y dentro por `nombre`.
- Solo servicios con al menos una foto o video (los sin media no aportan a la galería).

## Front + Go (aremko-cli) — los construyo en paralelo

- Go: proxy `GET /api/v1/inbox/media-library` → este endpoint; y el ENVÍO desde la
  biblioteca lo resuelvo descargando la URL pública y reenviándola por el canal
  (WhatsApp/IG/Messenger) con el flujo de envío de media que ya existe — **no requiere
  endpoint outbound nuevo de su lado**.
- Front: galería con miniaturas agrupadas (Tinas/Cabañas/Masajes) + buscador, en el
  compositor de los 3 canales, optimizada para celular.

⇒ Lo único que necesito de Django es `GET /api/inbox/media-library`. Apenas exista,
la galería se llena sola. Hoy el front tolera que no exista (muestra vacío/cargando).
