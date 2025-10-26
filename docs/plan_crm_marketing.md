## Plan de Trabajo: Módulo CRM y Marketing

Este documento registra el plan, el estado y las decisiones del proyecto de prospección B2B (Empresas Región de Los Lagos) y CRM/Marketing.

### Objetivo
- Cargar empresas/contactos por lotes y ejecutar una campaña de goteo por email cada 10 minutos con personalización por IA, respetando buenas prácticas de entregabilidad y opt-out.

### Estado de tareas
1. Crear documento de plan y templates CSV para CRM/Marketing — EN PROGRESO
2. Implementar importador CSV/Excel para Company y Contact (admin + CLI) — PENDIENTE
3. Crear plantillas CSV ejemplo y guía de limpieza/deduplicación — PENDIENTE
4. Sembrar Campaña “Prospección Los Lagos” en admin — PENDIENTE
5. Generar cola de envíos en CommunicationLog (status=PENDING) — PENDIENTE
6. Crear comando run_drip_campaign (batch, ventanas horarias, backoff) — PENDIENTE
7. Integrar AiCopyService (Deepseek) para variantes de asunto y apertura — PENDIENTE
8. Configurar cron en Render cada 10 minutos para la campaña — PENDIENTE
9. Agregar baja/opt-out y pie legal en plantillas de prospección — PENDIENTE
10. Dashboard básico de campaña: envíos, aperturas, respuestas — PENDIENTE
11. Pruebas end-to-end en dev con lote pequeño y métricas — PENDIENTE

### Alcance técnico
- Importadores: soportar CSV/Excel, deduplicar por `Company.name` y `Contact.email`, validación y reporte.
- Cola de envíos: usar `CommunicationLog` con `campaign`, `communication_type='EMAIL'`, `message_type='PROMOCIONAL'`, `status='PENDING'`.
- Comando de goteo: batch-size, ventana horaria (America/Santiago), límites diarios, reintentos, logging.
- IA de copy: generar asunto+apertura con límites de tokens, cache y trazabilidad.
- Entregabilidad: SPF/DKIM/DMARC, List-Unsubscribe, opt-out en pie, calentamiento de dominio.

### Decisiones abiertas
- Proveedor de tracking de aperturas/clics (fase 2) vs. mínimo viable sin píxel.
- Volumen por corrida (sugerido: 20–50) y tope diario inicial.

### Bitácora
- [yyyy-mm-dd] Documento creado y tareas iniciales definidas.

---
Mantener este documento actualizado al cerrar cada tarea.

