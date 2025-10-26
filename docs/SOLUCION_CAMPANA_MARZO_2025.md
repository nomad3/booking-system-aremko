# 🚨 Solución: Campaña "marzo 2025 hasta 100 mil" Estancada (44/88)

## 📋 **Problema Reportado**
- Campaña de email avanzada estancada en 44 de 88 emails enviados
- Se encuentra en: Admin → CRM & Marketing → Campañas Avanzadas

## 🔍 **Diagnóstico Inmediato**

### **Paso 1: Ejecutar Diagnóstico**
```bash
# En el servidor de Render (consola web):
python manage.py diagnose_email_campaign --campaign-name "marzo 2025 hasta 100 mil"

# O si conoces el ID exacto:
python manage.py diagnose_email_campaign --campaign-id [ID]

# Para ver todas las campañas:
python manage.py diagnose_email_campaign --list-all
```

### **Paso 2: Verificar Estado de la Campaña**
```bash
# Revisar qué campañas están activas:
python manage.py enviar_campana_email --auto --dry-run
```

## 🎯 **Soluciones Más Probables**

### **Solución 1: Reanudar Campaña Pausada**
```bash
# Si la campaña está pausada, reanudarla:
python manage.py enviar_campana_email --campaign-id [ID] --auto

# O forzar envío ignorando horarios:
python manage.py enviar_campana_email --campaign-id [ID] --ignore-schedule
```

### **Solución 2: Verificar Horario de Envío**
La campaña puede estar configurada para enviar solo en horarios específicos:
- **Horario típico**: 8:00-21:00 (hora de Chile)
- **Si estás fuera de horario**: Esperar o usar `--ignore-schedule`

### **Solución 3: Configurar Cron Job (Si No Existe)**
```bash
# Verificar que el cron esté configurado en Render:
*/6 * * * * cd /opt/render/project/src && python manage.py enviar_campana_email --auto >> /tmp/email_campaign.log 2>&1
```

### **Solución 4: Envío Manual por Lotes**
```bash
# Enviar un lote específico manualmente:
python manage.py enviar_campana_email --campaign-id [ID] --batch-size 10 --interval 1

# Modo seguro (pocas a la vez):
python manage.py enviar_campana_email --campaign-id [ID] --batch-size 5 --interval 3
```

## 🔧 **Comandos de Emergencia**

### **Verificar Destinatarios Pendientes**
```bash
# Ver estado general del sistema:
python manage.py shell -c "
from ventas.models import EmailCampaign, EmailRecipient
campaign = EmailCampaign.objects.filter(name__icontains='marzo 2025').first()
if campaign:
    print(f'Campaña: {campaign.name}')
    print(f'Estado: {campaign.get_status_display()}')
    print(f'Progreso: {campaign.emails_sent}/{campaign.total_recipients}')
    pending = EmailRecipient.objects.filter(campaign=campaign, status='pending', send_enabled=True).count()
    print(f'Pendientes: {pending}')
else:
    print('Campaña no encontrada')
"
```

### **Reactivar Campaña Completamente**
```bash
# Si todo falla, cambiar estado manualmente:
python manage.py shell -c "
from ventas.models import EmailCampaign
campaign = EmailCampaign.objects.filter(name__icontains='marzo 2025').first()
if campaign:
    campaign.status = 'sending'
    campaign.save()
    print(f'Campaña {campaign.name} reactivada a estado sending')
"
```

## 📊 **Configuración Típica para Esta Campaña**

```json
{
    "start_time": "08:00",
    "end_time": "21:00", 
    "batch_size": 5,
    "interval_minutes": 6,
    "timezone": "America/Santiago",
    "ai_enabled": true
}
```

## 🚀 **Pasos Recomendados AHORA**

1. **Diagnóstico**: Ejecutar `diagnose_email_campaign`
2. **Verificar horario**: ¿Estás en horario 8:00-21:00 Chile?
3. **Reanudar**: `enviar_campana_email --auto`
4. **Monitorear**: Revisar logs en 10-15 minutos

## 📞 **Si Nada Funciona**

```bash
# Envío forzado (usar con cuidado):
python manage.py enviar_campana_email --campaign-id [ID] --ignore-schedule --batch-size 10 --interval 2
```

## 📈 **Monitoreo Continuo**

```bash
# Ver progreso en tiempo real:
watch -n 30 'python manage.py diagnose_email_campaign --campaign-name "marzo 2025"'
```

---

**💡 TIP**: La campaña probablemente está pausada por horario o necesita ser reactivada manualmente. El diagnóstico te dirá exactamente qué hacer.