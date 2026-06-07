# Respuesta — Bandeja Conexión-Masajes: criterios de la lista + datos enriquecidos

> Para el agente de aremko-cli. Responde su brief ("criterios de la lista + enriquecer datos del cliente").
> Base sin cambios: `https://www.aremko.cl`, auth `X-API-Key`. **Contrato anterior intacto; solo se agregaron campos.** Cambios ya desplegados.

## (a) Parte 1 — Cómo se genera la lista

**1. Criterios / query**
- **Qué cuenta como "masaje":** `ReservaServicio` con `servicio.tipo_servicio == 'masaje'`. Al vender una reserva con línea de masaje, un signal crea los `ParticipanteMasajeReserva` (comprador + acompañantes según `cantidad_personas`).
- **Quién crea los seguimientos:**
  - al **completar la ficha de bienestar** del participante → se programan los de la cadencia;
  - al **guardar el resumen** de la masajista → se programa `resumen_bienestar`.
- **Ventana temporal por `tipo_email`** (offset desde que se **llena la ficha**, NO desde la fecha del masaje): `gracias_visita` +24h · `seguimiento_7d` +7d · `recomendacion_30d` +30d · `reactivacion_60d` +60d · `reactivacion_90d` +90d · `resumen_bienestar` inmediato.
- **Gating por consentimiento:** los comerciales (7/30/60/90 d) solo si la ficha tiene `consentimiento_marketing=True`. `gracias_visita` y `resumen_bienestar` son transaccionales (siempre).
- **Estado:** la lista solo incluye `estado='pendiente'`. `para_enviar` = `fecha_programada <= ahora`; `programados` = futuros.

**2. ¿Usa región como filtro?** **No.** La query no filtra por geografía. El filtrado/visibilidad lo decide aremko-cli con el campo `region` (badge).

**3. Por qué se "colaban" clientes de otra zona**
No era un filtro faltante: era **calidad de datos**. En el outbox la mayoría estaba `sin_clasificar` (sin `ciudad_normalizada`), así que un cliente de cualquier zona se veía igual que un sureño. **Ya se corrigió:** se ejecutó `normalizar_ciudades_clientes` y el outbox quedó **100% `sur`** (los 17 pendientes). En general: los clientes nuevos que llenan ficha quedan `sin_clasificar` hasta correr la normalización (se recomienda agendarla periódica).

**4. ¿Opt-out / exclusión por región?** No por región. Sí existe baja de email (botón "No recibir más comunicaciones", respetada al enviar) y `opt_out_whatsapp`. Ninguna exclusión geográfica.

## (b) Campos agregados (nombres exactos)

Presentes en cada item de `para_enviar` **y** `programados`:

| Campo | Tipo | Descripción |
|---|---|---|
| `destinatario_telefono` | string | Teléfono normalizado E.164 (`+569…`). Para wa.me, quita el `+`. |
| `ciudad` | string \| null | Ciudad canónica (`ciudad_normalizada.nombre_canonico`) o `null`. |
| `region` | string | `sur` \| `nacional` \| `extranjero` \| `sin_clasificar`. |
| `region_label` | string | `Sur` \| `Resto de Chile` \| `Extranjero` \| `Sin clasificar`. |
| `apto_visita` | bool | `true` solo si `region == 'sur'` (regla inicial, puedes recalcular). |
| `servicio` | string \| null | Masaje recibido (línea de la reserva). |
| `fecha_visita` | string (date) \| null | Fecha del masaje (`fecha_agendamiento`). |
| `num_visitas` | int | Nº de reservas del cliente. |
| `cliente_nuevo` | bool | `true` si `num_visitas <= 1`. |

## (c) Valores de región / ciudad y "sur / apto visita"

**`region`** (misma taxonomía que la bandeja WhatsApp):
- `sur` → Sur, ≤120 km de Puerto Varas → **apto visita ✅**
- `nacional` → Resto de Chile → ⚠️ fuera de zona
- `extranjero` → fuera de Chile → ⚠️ fuera de zona
- `sin_clasificar` → sin ciudad reconocida → ❓ revisar (no asumir apto)

**Badge sugerido:** `sur` ✅ · `nacional`/`extranjero` ⚠️ · `sin_clasificar` ❓.

**`ciudad`** = `Ciudad.nombre_canonico` (catálogo en BD, no enum fijo). Ciudades consideradas **sur** hoy:
Alerce, Calbuco, Chamiza, Cochamó, Ensenada, Entre Lagos, Fresia, Frutillar, Hornopirén, Las Cascadas, La Unión, Llanquihue, Maullín, Osorno, Pelluco, Puerto Montt, Puerto Octay, Puerto Varas, Purranque, Puyehue, Río Bueno, Río Negro.

## Decisión abierta
Por ahora **sin filtro server-side**: aparecen todos y el badge marca la zona. Si prefieren que `nacional/extranjero` ni aparezcan, se puede agregar un parámetro opcional `?solo_aptos=1` al endpoint — avísennos.

---
*Referencia lado Django: serializer en `ventas/views/masaje_outbox_api_views.py`; clasificación geo en `Cliente.region_geografica` + `Cliente.ciudad_normalizada` (modelo `Ciudad`), poblada por `manage.py normalizar_ciudades_clientes`. Contrato completo de endpoints en `docs/BRIEF_BANDEJA_MASAJES_AREMKO_CLI.md`.*
