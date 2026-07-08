# Pendientes Aremko (backlog vivo)

Lista única de temas pendientes Jorge ↔ Claude. **Uso:** al completar un tema se
ELIMINA de la lista (git guarda la historia); los IDs `P-xx` son estables y no se
reutilizan. Para agregar: "agrega a pendientes: …". Para cerrar: "listo el P-xx".
Claude la revisa al inicio de sesión y en cada wrapup.

_Última revisión: 2026-07-08_

## Web y marketing

1. **P-01 · Video hero de la portada** — Infra LISTA en prod (campo `hero_video`
   en Admin → Configuración de la Homepage; la portada lo reproduce de fondo con
   la foto de respaldo). **Solo falta que Jorge suba** `hero_masajes_web.mp4` (1.3 MB,
   listo) por ese campo del admin y Guardar (Django lo manda a Cloudinary solo).
2. **P-02 · Fotos definitivas a carruseles GiftCards** — Reemplazar fotos provisorias
   de las 4 experiencias insignia. Hay 80 fotos optimizadas en `*/_web/` del disco
   JAguilera.
3. **P-03 · Video hero landing masajes** — Grabar el plano secuencia del recorrido
   (recepción → pasarelas → domos → mirador, 15–25 s, con audio del río) según la
   shot-list de `docs/PROPUESTA_LANDING_MASAJES.md`. El clip corto que existía se
   destinó a la portada (P-01).
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
