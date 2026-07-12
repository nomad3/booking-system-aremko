# Pendientes Aremko (backlog vivo)

Lista única de temas pendientes Jorge ↔ Claude. **Uso:** al completar un tema se
ELIMINA de la lista (git guarda la historia); los IDs `P-xx` son estables y no se
reutilizan. Para agregar: "agrega a pendientes: …". Para cerrar: "listo el P-xx".
Claude la revisa al inicio de sesión y en cada wrapup.

_Última revisión: 2026-07-11_

## Web y marketing

2. **P-02 · Fotos definitivas a carruseles GiftCards** — Reemplazar fotos provisorias
   de las 4 experiencias insignia. Hay 80 fotos optimizadas en `*/_web/` del disco
   JAguilera.
4. **P-04 · Menú/navegación limpia site-wide** — La home boutique ya tiene menú
   limpio; falta extenderlo al resto del sitio.
5. **P-05 · Campañas Ritual + Pausa en Meta y Google** — Arrancar verificando los
   paneles (plan 2026-06-26). El material de Pausa (keywords, RSA, anuncios) quedó
   listo en aremko-cli.
6. **P-06 · GiftCards F2/F3** — Entrega programada, canje conversacional con Luna,
   bonus estacional y campañas de email de giftcards.

## Pagos y conciliador

7. **P-07 · Activar auto-aplicar del Conciliador** — Tras ~2 semanas de calibración
   supervisada (desde 2026-07-06 → revisar ~2026-07-20): matches únicos se aplican
   solos, Deborah solo mira los "revisar".
8. **P-08 · Limpiar tanda histórica del Conciliador** — Deborah marca "Ignorar" los
   movimientos antiguos ya registrados a mano, para dejar la cola en cero.
9. **P-09 · Decisión Flow → MP en el checkout web** — Hoy conviven; definir si el
   carrito público migra a Mercado Pago (cuotas también en la web).
10. **P-10 · Reserva de prueba #6221** — Anular/reembolsar desde el panel MP los
    $2.500 reales del test de cuotas, para no ensuciar métricas.
16. **P-16 · Boletas electrónicas SII automáticas** — **F1 DESPLEGADA 2026-07-11**
    (app `facturacion/` en ambiente simulado: MedioPago con switch genera_boleta,
    emisor idempotente vía SimpleAPI, acción "Emitir boleta" en Pagos, página
    pública /boletas/consulta/, diagnóstico --smoke). Detalle y runbook completo:
    `docs/BRIEF_P-16_boletas_sii.md`. Siguiente — pasos de Jorge: (1) cuenta
    gratis simpleapi.cl → API key a Render `SIMPLEAPI_API_KEY`; (2) certificado
    .pfx → `SII_CERT_B64` + `SII_CERT_PASSWORD`; (3) solicitar set de pruebas de
    boleta en sii.cl; (4) contador confirma exclusividad portal gratuito ↔
    software propio. Luego Claude: certificación en ambiente cert + F2
    (emisión automática con cola) + F3 (notas de crédito).
    F1: app `facturacion/` + tabla `MedioPago` con flag `genera_boleta` (siembra de
    los 21 métodos, editable en admin; pedido por Jorge para evitar dobles boleteos)
    + botón manual. F2: señal post_save(Pago) + cola (patrón conciliador) + candado
    1-a-1 boleta↔pago. F3: notas de crédito + cuadratura mensual.

## Infraestructura y Luna

11. **P-11 · Logging de errores 500 en Render** — Agregar handler para el logger
    `django.request` (hoy los 500 no dejan traceback; se diagnostican con
    `diagnosticar_admin_add --url`).
12. **P-12 · Luna FASE 3 y 4** — Cron de seguimiento de propuestas + combos en el
    carrito.
13. **P-13 · Máquina de reseñas Google** — Pedir reseña post-visita vía Luna
    (diseñada en plan, no iniciada).
14. **P-14 · Tina Calbuco para grupos de 3** — Configurar `capacidad_minima=3`
    ($75.000 para 3 personas) en el admin.
15. **P-15 · WhatsApp Cloud API / Meta** — Destrabar App Review (decidir App propio
    vs BSP) y rotar el APP_SECRET de la bandeja de Instagram.
