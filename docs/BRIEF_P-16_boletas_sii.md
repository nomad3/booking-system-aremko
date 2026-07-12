# BRIEF P-16 · Boletas electrónicas SII automáticas (SimpleAPI)

_Estado al 2026-07-11 — F1 desplegada en ambiente **simulado**. Pendiente: cuenta
SimpleAPI + certificado + certificación SII (runbook abajo)._

## Contexto y alcance tributario (confirmado por Jorge 2026-07-11)

- **Solo generan boleta** los pagos por **transferencia y efectivo** — incluida la
  transferencia directa a la **Cuenta Vista de Mercado Pago**.
- **NO generan boleta**: tarjeta (SumUp), Webpay, Flow, **links de pago MP** — el
  recaudador informa al SII y el voucher reemplaza la boleta (F29).
- **GiftCard**: la venta NO boletea por sí misma — es un producto más (como una
  tabla de quesos): boletea o no **según el medio con que se pagó** esa compra.
  El **canje** (`metodo_pago='giftcard'`) nunca boletea.
- **Una boleta por cada pago** (en servicios el IVA se devenga al percibir).
- `booking` queda fuera (lo gestiona el contador aparte).
- Volumen esperado: **~200 boletas/mes**.

## Ruta elegida

**SimpleAPI** (api.simpleapi.cl) — plan **gratis 500 consultas/mes**; upgrade
5 UF/año (10.000/mes) si no alcanza. Descartada la integración directa al SII
(certificación XML/folios a mano) y OpenFactura ($360k/año) por costo.

### Contrato de la API (verificado en documentacion.simpleapi.cl, 2026-07-11)

- Auth: header `Authorization: <ApiKey>`.
- `POST /api/v1/dte/generar` (multipart): `input` = JSON del Documento
  (Encabezado/Detalles + `Certificado{Rut,Password}`), `files` = certificado
  `.pfx`, `files2` = CAF `.xml`. Respuesta 200 = XML del DTE firmado/timbrado.
- Boleta 39: `IndicadorServicio=3`, receptor `66666666-6`, montos brutos
  (neto = total/1.19).
- Rate limit DTE: 3/s, 40/min. API "Folios" aparte para pedir CAF (5/min).
- Endpoints de **sobre + envío al SII** están en la carpeta "Envio de DTE" de la
  colección Postman; los paths exactos se fijan en la sesión de certificación
  (constantes en `facturacion/services/simpleapi_client.py`).

## Arquitectura (app `facturacion/`, aislada drift-safe)

| Pieza | Qué hace |
|---|---|
| `MedioPago` | Switch `genera_boleta` por medio (anti doble boleteo, editable en admin). Sembrado: 22 medios, 14 boletean. |
| `ConfiguracionFacturacion` | Singleton: ambiente (simulado/certificación/producción), datos del emisor, `emision_automatica` (F2, apagado). |
| `RangoFolios` | CAF del SII: rango + folio_siguiente (asignación atómica con `select_for_update`). |
| `BoletaElectronica` | OneToOne con `ventas.Pago` (**candado anti-duplicado a nivel BD**) + PROTECT (no se puede borrar un pago boleteado → nota de crédito en F3). |
| `services/emisor.py` | `emitir_boleta_para_pago(pago)`: idempotente; valida medio/monto; simulado → marca; real → folio CAF + SimpleAPI; errores quedan en la boleta (estado `error`, reintentable). Glosa con savepoint (jamás aborta la transacción del caller). |
| Admin | Panel boletas (badge estado, reintento, XML), acción **"Emitir boleta electrónica (P-16)"** en Pagos, medios editables, config, folios con alerta de restantes. |
| Página pública | `/boletas/consulta/` (folio+monto) y `/boletas/b/<token>/` — **requisito de la declaración de cumplimiento SII** (link de consulta). |
| Diagnóstico | `python manage.py diagnostico_facturacion [--smoke]` — smoke con **rollback** (seguro en prod, usa un pago existente y no persiste nada). |

Secretos SOLO por entorno (Render): `SIMPLEAPI_API_KEY`, `SII_CERT_B64`
(.pfx en base64), `SII_CERT_PASSWORD`. Nada en BD ni en el repo.

## Runbook de certificación (para pasar de simulado a real)

**Lado Jorge (una vez):**
1. Crear cuenta gratis en simpleapi.cl → obtener **API key** → pegarla en Render
   → Environment → `SIMPLEAPI_API_KEY` (no por chat).
2. Exportar el **certificado digital** del representante legal a `.pfx`:
   `base64 -i certificado.pfx | pbcopy` → Render `SII_CERT_B64`; la clave en
   `SII_CERT_PASSWORD`.
3. En sii.cl (rep. legal): **solicitar el set de pruebas** de boleta electrónica.

**Lado Claude (siguiente sesión):**
4. Completar `ConfiguracionFacturacion` (RUT emisor, razón social, giro,
   dirección, RUT firmante) y cambiar ambiente a `certificacion`.
5. Pedir **CAF de certificación** (folios de prueba) → cargar en `RangoFolios`.
6. Ejecutar el **set de pruebas** emitiendo por el admin; fijar los paths de
   sobre/envío con la colección Postman; enviar las muestras al SII
   (SII_BE_Certificacion@sii.cl según instructivo).
7. Con el V°B° (10-15 días hábiles): Jorge hace la **declaración de
   cumplimiento** (link de consulta = `https://www.aremko.cl/boletas/consulta/`).
8. **Switch a producción** (fecha D): pedir CAF real, ambiente `produccion`,
   y desde ahí transferencia/efectivo se boletea por el sistema.
   ⚠️ Antes del switch confirmar con el contador/SII la **exclusividad** con el
   portal gratuito (FAQ sugiere que no conviven para boletas).

## Verificación F1 (2026-07-11)

- Local (Docker): `manage.py check` 0 issues; migración 0001 (a mano) aplica
  limpia; `sembrar_medios_pago` → 22/14; `/boletas/consulta/` HTTP 200.
- Prod: migración vía Render job + siembra + `diagnostico_facturacion --smoke`
  (ver resultado en el hilo del 2026-07-11).

## Hallazgos de entorno (no bloquean, anotados)

- La BD local del docker-compose tiene el **registro de migraciones desfasado**
  (se normalizó con `migrate --fake` local). La suite `manage.py test` con BD
  fresca sigue rota por el drift AR-033/34 de ventas (pre-existente).
- El servicio `web` del compose local no levanta con su entrypoint completo
  (migrate+collectstatic); para smoke usar
  `docker-compose run --rm -p 8005:8000 web python manage.py runserver --noreload`.

## F2 (siguiente) y F3

- **F2**: señal `post_save(Pago)` + cola de emisión (patrón conciliador:
  botón admin + endpoint cron con `X-API-KEY`) + boleta en el email al cliente +
  espejo del folio en `VentaReserva.numero_documento_fiscal`.
- **F3**: notas de crédito (61) para anulaciones + cuadratura mensual para el
  contador + alerta de folios por agotarse.
