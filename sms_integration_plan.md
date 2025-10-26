# Plan de Integración SMS + Email para Aremko CRM

## 🎯 Objetivo
Implementar comunicación inteligente via SMS (Redvoiss) y Email optimizado, evitando spam mediante segmentación avanzada y triggers contextuales.

## 📊 Análisis del Sistema Actual

### ✅ Fortalezas Existentes:
- Sistema de campañas robusto con plantillas SMS/Email
- Segmentación automática en 9 categorías
- Tracking de interacciones implementado
- Modelos Campaign y CampaignInteraction preparados

### 🔧 Áreas de Mejora:
- Falta integración con proveedor SMS real
- No hay triggers automáticos contextales
- Email genérico sin personalización avanzada
- No hay límites de frecuencia para evitar spam

## 🚀 Propuesta de Implementación

### FASE 1: Integración SMS Redvoiss (2-3 semanas)

#### 1.1 Configuración Inicial
```python
# settings.py - Nuevas configuraciones
REDVOISS_API_URL = os.getenv('REDVOISS_API_URL')
REDVOISS_API_KEY = os.getenv('REDVOISS_API_KEY')
REDVOISS_USERNAME = os.getenv('REDVOISS_USERNAME')

# Límites anti-spam
SMS_DAILY_LIMIT_PER_CLIENT = 2
SMS_MONTHLY_LIMIT_PER_CLIENT = 8
EMAIL_WEEKLY_LIMIT_PER_CLIENT = 1
```

#### 1.2 Nuevo Servicio SMS
```python
# ventas/services/sms_service.py
class RedvoissService:
    def send_sms(self, phone, message, campaign_id=None):
        # Verificar límites antes de enviar
        # Integrar con API Redvoiss
        # Registrar en CampaignInteraction
```

#### 1.3 Sistema de Límites Anti-Spam
```python
# ventas/models.py - Nuevos modelos
class CommunicationLimit(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    sms_count_daily = models.IntegerField(default=0)
    sms_count_monthly = models.IntegerField(default=0)
    email_count_weekly = models.IntegerField(default=0)
    last_sms_date = models.DateField(null=True)
    last_email_date = models.DateTimeField(null=True)
```

### FASE 2: Triggers Contextuales (1-2 semanas)

#### 2.1 SMS Automáticos
- **Confirmación reserva** (inmediato)
- **Recordatorio cita** (24h antes)
- **Cumpleaños** (1 vez por año máximo)
- **Reactivación** (solo después 90 días inactividad)

#### 2.2 Email Segmentado
- **Serie bienvenida** (nuevos clientes)
- **Newsletter VIP** (solo high spenders, 1 vez/mes)
- **Reactivación** (inactivos 90+ días, máximo 1 vez/trimestre)

### FASE 3: Dashboard de Comunicaciones (1 semana)

#### 3.1 Panel de Control
- Métricas de entrega SMS/Email
- Límites por cliente en tiempo real
- Segmentos con comunicación pendiente
- ROI de campañas por segmento

### FASE 4: Optimizaciones Avanzadas (1-2 semanas)

#### 4.1 Inteligencia Artificial
- **Mejor momento envío**: Análisis horarios de mayor engagement
- **Personalización avanzada**: Recomendaciones basadas en historial
- **Predicción churn**: Identificar clientes en riesgo de abandono

## 🛡️ Estrategias Anti-Spam

### 1. Límites de Frecuencia
```python
COMMUNICATION_LIMITS = {
    'sms_per_day': 2,
    'sms_per_month': 8,
    'email_per_week': 1,
    'birthday_sms_per_year': 1,
    'reactivation_email_per_quarter': 1
}
```

### 2. Segmentación Inteligente
```python
# Solo enviar a segmentos relevantes
COMMUNICATION_SEGMENTS = {
    'birthday_sms': ['all_segments_except_zero_spend'],
    'loyalty_newsletter': ['vip_high_spend', 'regular_high_spend'],
    'win_back_email': ['inactive_90_days'],
    'booking_reminders': ['active_customers_only']
}
```

### 3. Opt-out Automático
```python
# Sistema de baja automática
class ClientPreferences(models.Model):
    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE)
    accepts_sms = models.BooleanField(default=True)
    accepts_email = models.BooleanField(default=True)
    accepts_birthday_sms = models.BooleanField(default=True)
    accepts_promotional = models.BooleanField(default=True)
```

## 💡 Casos de Uso Específicos

### 1. Cliente Nuevo (Primera Reserva)
```
1. SMS confirmación reserva → ✅ Inmediato
2. Email bienvenida serie (3 emails) → ✅ Días 1, 7, 30
3. SMS recordatorio cita → ✅ 24h antes
4. Email seguimiento satisfacción → ✅ 24h después del servicio
```

### 2. Cliente VIP (6+ visitas, alto gasto)
```
1. SMS cumpleaños con descuento especial → ✅ 1 vez/año
2. Email newsletter mensual exclusivo → ✅ 1 vez/mes
3. SMS early access nuevos servicios → ✅ Máximo 2/mes
4. Email recompensas fidelidad → ✅ Trimestral
```

### 3. Cliente Inactivo (90+ días)
```
1. Email reactivación personalizado → ✅ 1 vez/trimestre
2. SMS oferta especial retorno → ✅ Solo si no responde email
3. Llamada personal (registro manual) → ✅ Si es VIP
```

## 📊 Métricas de Éxito

### KPIs Principales:
- **Tasa apertura SMS**: >95%
- **Tasa apertura Email**: >25%
- **Tasa conversión reactivación**: >10%
- **Quejas spam**: <0.1%
- **Opt-out rate**: <2%

### Reportes Automáticos:
- Dashboard tiempo real con métricas
- Reporte semanal ROI por segmento
- Alerta automática si excedem límites spam

## 🔧 Aspectos Técnicos

### Variables de Entorno Nuevas:
```bash
# Redvoiss SMS
REDVOISS_API_URL=https://api.redvoiss.com/sms
REDVOISS_API_KEY=tu_api_key
REDVOISS_USERNAME=tu_usuario

# Email mejorado  
EMAIL_HOST=smtp.gmail.com  # o proveedor que elijas
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=comunicaciones@aremko.cl

# Límites anti-spam
SMS_DAILY_LIMIT=2
EMAIL_WEEKLY_LIMIT=1
```

### Nuevas Dependencias:
```
requests>=2.28.0  # Para API Redvoiss
celery>=5.2.0     # Para tasks asíncronas
django-celery-beat>=2.4.0  # Para scheduling
```

## 💰 Estimación Costos

### Desarrollo (40-60 horas):
- Integración Redvoiss: 15-20h
- Sistema límites anti-spam: 10-15h  
- Triggers automáticos: 10-15h
- Dashboard comunicaciones: 5-10h

### Operativos Mensuales:
- SMS Redvoiss: ~$0.05-0.08 USD por SMS
- Email service: ~$20-50 USD/mes
- Total estimado: $100-200 USD/mes (para 1000 clientes activos)

## 🚀 Beneficios Esperados

### Para el Negocio:
- **+30% retención clientes** con comunicación personalizada
- **+20% ventas repeat** con recordatorios y ofertas inteligentes  
- **+40% satisfacción** con comunicación relevante y no intrusiva
- **-80% quejas spam** con límites y segmentación

### Para los Clientes:
- Comunicación relevante y oportuna
- No saturación de mensajes
- Ofertas personalizadas según perfil
- Recordatorios útiles de citas

## 📅 Timeline Propuesto

**Semana 1-2**: Investigación API Redvoiss + Setup básico
**Semana 3-4**: Integración SMS + Sistema límites  
**Semana 5-6**: Triggers automáticos + Email mejorado
**Semana 7**: Dashboard + Testing
**Semana 8**: Deploy producción + Monitoreo

¿Te parece bien este enfoque? ¿Quieres que empecemos con la integración de Redvoiss?