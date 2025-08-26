---
name: Módulo IA Fase 1 – Checklist
about: Seguimiento de implementación del Módulo IA (Chat IA, Recomendaciones, Copiloto de campañas)
title: "Módulo IA – Fase 1: Implementación"
labels: enhancement, IA, phase1
assignees: ''
---

## Objetivo
Implementar la Fase 1 del Módulo IA: Chat de negocio (Deepseek + SQL readonly), Recomendaciones por cliente y Copiloto de campañas.

## Checklist
- [ ] Configurar variables de entorno (`DEEPSEEK_API_KEY`, límites de costo, roles permitidos).
- [ ] Implementar integración con Deepseek (server-side) y herramientas `query_sql_readonly` y `get_kpi`.
- [ ] Definir y probar 10 plantillas SQL canónicas (whitelist) con validación de parámetros.
- [ ] Crear vistas/materialized views para KPIs usados por el chat.
- [ ] Añadir menú “IA” y pantalla de Chat de negocio en el dashboard.
- [ ] Añadir panel “Sugerencias IA” en la ficha de `Cliente`.
- [ ] Implementar Copiloto de campañas (generación de copy + segmento sugerido, sin envío masivo automático por defecto).
- [ ] Agregar logs estructurados (pregunta, plantilla, parámetros, costo, duración, filas) y panel básico de uso/costo.
- [ ] Pruebas internas con usuarios `admin`/`marketing` y ajuste de límites.
- [ ] Habilitar en producción (feature flag `AI_FEATURES_ENABLED=true`).

## Referencias
- Documento funcional/técnico: `docs/modulo_ia.md`

## Notas
- Alcance de seguridad: consultas en modo solo lectura; sin escrituras.
- Respetar límites anti-spam y preferencias de contacto en cualquier salida que derive en email/SMS.
