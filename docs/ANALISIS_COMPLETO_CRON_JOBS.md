# 🔍 Análisis Completo de Cron Jobs - Migración a cron-job.org

**Fecha**: 11 de noviembre, 2025
**Objetivo**: Identificar TODOS los cron jobs en Render y migrarlos a cron-job.org

---

## 📊 Estado Actual

### ✅ YA MIGRADOS A cron-job.org

| # | Módulo | Cron Job | Frecuencia | Endpoint HTTP | Estado |
|---|--------|----------|------------|---------------|--------|
| 1 | Control Gestión | Preparación Servicios | Cada 15 min | `/control_gestion/cron/preparacion-servicios/` | ✅ ACTIVO |
| 2 | Control Gestión | Vaciado Tinas | Cada 30 min | `/control_gestion/cron/vaciado-tinas/` | ✅ ACTIVO |
| 3 | Control Gestión | Apertura Diaria | 7:00 AM | `/control_gestion/cron/daily-opening/` | ✅ ACTIVO |
| 4 | Control Gestión | Reporte Matutino | 9:00 AM | `/control_gestion/cron/daily-reports/?momento=matutino` | ✅ ACTIVO |
| 5 | Control Gestión | Reporte Vespertino | 6:00 PM | `/control_gestion/cron/daily-reports/?momento=vespertino` | ✅ ACTIVO |

**Documentación**: `docs/ESTADO_CRON_JOBS.md`

---

### ✅ RECIÉN IMPLEMENTADOS (pendientes de configurar)

| # | Módulo | Cron Job | Frecuencia | Endpoint HTTP | Estado |
|---|--------|----------|------------|---------------|--------|
| 6 | Premios | Procesar Premios Bienvenida | 8:00 AM diario | `/ventas/cron/procesar-premios-bienvenida/` | ⚠️ PENDIENTE CONFIG |
| 7 | Premios | Enviar Premios Aprobados | Cada 30 min | `/ventas/cron/enviar-premios-aprobados/` | ⚠️ PENDIENTE CONFIG |

**Documentación**: `docs/MIGRACION_CRON_PREMIOS.md`

---

### ⚠️ PENDIENTES DE MIGRAR

#### 1️⃣ Envío de Emails Programados

**Comando**: `python manage.py enviar_emails_programados`

**Archivo**: `ventas/management/commands/enviar_emails_programados.py`

**Qué hace**:
- Envía emails de campañas que están en cola (modelo `MailParaEnviar`)
- **Rate limiting**: Batch de 2 emails por ejecución (configurable con --batch-size)
- **Horario permitido**: 8:00 AM - 6:00 PM (horario Chile)
- **Control anti-spam**: Respeta prioridad y orden de creación
- Estados: PENDIENTE → ENVIADO/ERROR

**Uso actual**:
```bash
# Default (2 emails)
python manage.py enviar_emails_programados

# Custom batch
python manage.py enviar_emails_programados --batch-size 5

# Ignorar horario (testing)
python manage.py enviar_emails_programados --ignore-schedule
```

**Frecuencia recomendada**: **Cada 30 minutos** (8:00 AM - 6:00 PM)
- Cron: `*/30 8-17 * * *`

**Endpoint a crear**: `/ventas/cron/enviar-emails-programados/`

**Estado**: ⚠️ **PENDIENTE** (endpoint no existe)

---

#### 2️⃣ Triggers de Comunicación Automática

**Comando**: `python manage.py send_communication_triggers`

**Archivo**: `ventas/management/commands/send_communication_triggers.py`

**Qué hace**:
- Sistema completo de comunicación inteligente con SMS (Redvoiss) y Email
- **5 tipos de triggers automáticos**:
  1. **Recordatorios** (`--type reminders`): SMS/Email 24h antes de reserva
  2. **Encuestas** (`--type surveys`): Encuesta satisfacción 24h después del servicio
  3. **Cumpleaños** (`--type birthdays`): Felicitación cumpleaños (1 vez/año máximo)
  4. **Reactivación** (`--type reactivation`): Email a clientes inactivos 90+ días (1 vez/trimestre)
  5. **Newsletter VIP** (`--type vip`): Newsletter mensual para clientes premium

**Características**:
- ✅ Anti-spam robusto: Límites 2 SMS/día, 8 SMS/mes, 1 email/semana
- ✅ Respeta horarios: 9:00 AM - 8:00 PM
- ✅ Preferencias opt-out por tipo de comunicación
- ✅ Integración Redvoiss SMS (₡12 CLP/SMS)
- ✅ Logs detallados y tracking de costos

**Uso actual**:
```bash
# Todos los tipos
python manage.py send_communication_triggers --type all

# Tipos específicos
python manage.py send_communication_triggers --type reminders
python manage.py send_communication_triggers --type birthdays
python manage.py send_communication_triggers --type surveys
python manage.py send_communication_triggers --type reactivation
python manage.py send_communication_triggers --type vip

# Dry-run (simular sin enviar)
python manage.py send_communication_triggers --type all --dry-run
```

**Frecuencias recomendadas**:

| Tipo | Frecuencia | Cron | Descripción |
|------|------------|------|-------------|
| `reminders` | Cada hora | `0 * * * *` | Recordatorios 24h antes |
| `surveys` | Diario 11:00 AM | `0 11 * * *` | Encuestas post-servicio |
| `birthdays` | Diario 10:00 AM | `0 10 * * *` | Cumpleaños del día |
| `reactivation` | Lunes 9:00 AM | `0 9 * * 1` | Reactivar inactivos |
| `vip` | 1er día mes 9:00 AM | `0 9 1 * *` | Newsletter mensual VIP |

**Endpoints a crear**:
- `/ventas/cron/triggers-reminders/`
- `/ventas/cron/triggers-surveys/`
- `/ventas/cron/triggers-birthdays/`
- `/ventas/cron/triggers-reactivation/`
- `/ventas/cron/triggers-vip/`

**Documentación**: `COMUNICACION_INTELIGENTE_README.md` (líneas 88-105)

**Estado**: ⚠️ **PENDIENTE** (endpoints no existen)

---

### ❌ COMANDOS QUE NO SON CRON JOBS

Estos comandos son de uso manual o testing, **NO necesitan migración**:

| Comando | Propósito | Tipo |
|---------|-----------|------|
| `enviar_campana_email.py` | Envío manual de campañas específicas | Manual |
| `enviar_campana_giftcard.py` | Envío manual gift cards | Manual |
| `run_january_campaign.py` | Campaña específica enero (one-time) | One-time |
| `send_campaign_test_email.py` | Testing de templates | Testing |
| `diagnose_campaign_queue.py` | Diagnóstico de cola | Diagnóstico |
| `diagnose_email.py` | Test envío emails | Testing |
| `test_email_sending.py` | Test email service | Testing |
| `test_redvoiss.py` | Test integración SMS | Testing |

---

## 📋 Resumen de Migración Necesaria

### Total de Cron Jobs Identificados: **9**

| Estado | Cantidad | Cron Jobs |
|--------|----------|-----------|
| ✅ Migrados y activos | 5 | Control Gestión (5) |
| ⚠️ Implementados, pendiente config | 2 | Premios (2) |
| ❌ Pendientes de implementar | 2 | Emails Programados (1) + Triggers (1 con 5 variantes) |

---

## 🔧 Plan de Migración Pendiente

### FASE 1: Premios (IMPLEMENTADO - Falta configurar)

✅ **Archivos creados**:
- `ventas/views/cron_views.py`
- Rutas agregadas a `ventas/urls.py`

⚠️ **Falta**:
- Configurar en cron-job.org (2 jobs)

**Prioridad**: 🔴 ALTA

---

### FASE 2: Emails Programados (PENDIENTE)

❌ **Archivos a crear**:
- Agregar endpoint `cron_enviar_emails_programados()` en `ventas/views/cron_views.py`
- Agregar ruta en `ventas/urls.py`

❌ **Configurar en cron-job.org**:
- 1 job: Cada 30 min (solo 8:00 AM - 6:00 PM)

**Prioridad**: 🟡 MEDIA

---

### FASE 3: Triggers de Comunicación (PENDIENTE)

❌ **Archivos a crear**:
- Agregar 5 endpoints en `ventas/views/cron_views.py`:
  - `cron_triggers_reminders()`
  - `cron_triggers_surveys()`
  - `cron_triggers_birthdays()`
  - `cron_triggers_reactivation()`
  - `cron_triggers_vip()`
- Agregar 5 rutas en `ventas/urls.py`

❌ **Configurar en cron-job.org**:
- 5 jobs con diferentes frecuencias

**Prioridad**: 🟡 MEDIA-ALTA (depende del uso del sistema de comunicación)

---

## 📊 Estado Final Esperado

### Tabla Completa de Cron Jobs (9 total)

| # | Módulo | Cron Job | Frecuencia | Endpoint HTTP | Estado |
|---|--------|----------|------------|---------------|--------|
| 1 | Control Gestión | Preparación Servicios | Cada 15 min | `/control_gestion/cron/preparacion-servicios/` | ✅ ACTIVO |
| 2 | Control Gestión | Vaciado Tinas | Cada 30 min | `/control_gestion/cron/vaciado-tinas/` | ✅ ACTIVO |
| 3 | Control Gestión | Apertura Diaria | 7:00 AM | `/control_gestion/cron/daily-opening/` | ✅ ACTIVO |
| 4 | Control Gestión | Reporte Matutino | 9:00 AM | `/control_gestion/cron/daily-reports/?momento=matutino` | ✅ ACTIVO |
| 5 | Control Gestión | Reporte Vespertino | 6:00 PM | `/control_gestion/cron/daily-reports/?momento=vespertino` | ✅ ACTIVO |
| 6 | Premios | Procesar Premios Bienvenida | 8:00 AM | `/ventas/cron/procesar-premios-bienvenida/` | ⚠️ PENDIENTE CONFIG |
| 7 | Premios | Enviar Premios Aprobados | Cada 30 min | `/ventas/cron/enviar-premios-aprobados/` | ⚠️ PENDIENTE CONFIG |
| 8 | Emails | Enviar Emails Programados | Cada 30 min (8-18h) | `/ventas/cron/enviar-emails-programados/` | ❌ PENDIENTE |
| 9 | Comunicación | Triggers Recordatorios | Cada hora | `/ventas/cron/triggers-reminders/` | ❌ PENDIENTE |
| 10 | Comunicación | Triggers Encuestas | Diario 11:00 AM | `/ventas/cron/triggers-surveys/` | ❌ PENDIENTE |
| 11 | Comunicación | Triggers Cumpleaños | Diario 10:00 AM | `/ventas/cron/triggers-birthdays/` | ❌ PENDIENTE |
| 12 | Comunicación | Triggers Reactivación | Lunes 9:00 AM | `/ventas/cron/triggers-reactivation/` | ❌ PENDIENTE |
| 13 | Comunicación | Triggers Newsletter VIP | 1er día mes 9:00 AM | `/ventas/cron/triggers-vip/` | ❌ PENDIENTE |

**Total real**: 13 cron jobs (5 activos + 2 pendientes config + 6 pendientes implementar)

---

## 🎯 Próximos Pasos Recomendados

### Opción 1: Migración Inmediata Completa

1. ✅ Configurar premios en cron-job.org (10 min)
2. Crear endpoints para emails programados (20 min)
3. Crear endpoints para triggers comunicación (40 min)
4. Configurar todos en cron-job.org (20 min)

**Tiempo total**: ~90 minutos
**Beneficio**: Todo centralizado y funcionando

---

### Opción 2: Migración Gradual (Recomendado)

**Hoy**:
- ✅ Configurar premios en cron-job.org (crítico para funcionamiento)

**Esta semana**:
- Implementar endpoints emails programados
- Configurar en cron-job.org

**Próxima semana** (si se usa el sistema de comunicación):
- Implementar endpoints triggers
- Configurar en cron-job.org

**Tiempo total**: Distribuido, menos riesgo

---

## ❓ Preguntas para el Usuario

Antes de continuar con la migración, necesito saber:

1. **¿Está usando activamente el sistema de comunicación inteligente?**
   - Si NO: No migrar triggers (prioridad baja)
   - Si SÍ: Migrar triggers (prioridad alta)

2. **¿Está usando campañas de email con `MailParaEnviar`?**
   - Si NO: No migrar enviar_emails_programados
   - Si SÍ: Migrar (prioridad media)

3. **¿Qué configuración de Render Cron Jobs tiene actualmente?**
   - Para verificar cuáles están realmente en uso

---

## 📚 Archivos Relacionados

- `docs/ESTADO_CRON_JOBS.md` - Cron jobs de Control Gestión
- `docs/MIGRACION_CRON_PREMIOS.md` - Migración de premios
- `COMUNICACION_INTELIGENTE_README.md` - Sistema de comunicación
- `ventas/management/commands/enviar_emails_programados.py`
- `ventas/management/commands/send_communication_triggers.py`
- `ventas/management/commands/procesar_premios_bienvenida.py`
- `ventas/management/commands/enviar_premios_aprobados.py`

---

**Última actualización**: 11 de noviembre, 2025
**Status**: ⚠️ Migración parcial completada (5/13 jobs migrados)
**Próxima acción**: Configurar premios en cron-job.org + decisión sobre otros módulos
