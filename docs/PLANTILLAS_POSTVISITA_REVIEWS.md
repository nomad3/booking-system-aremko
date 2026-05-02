# Plantillas Post-Visita — Solicitar Reseña Google

**Para:** mensaje WhatsApp + email automático que sale 24h después del checkout

---

## 📱 WhatsApp (texto plano, con emojis sutiles)

**Cuándo:** 24 horas después del checkout
**Quién recibe:** todos los clientes con teléfono registrado y `permite_sms=True`
**Asunto:** —

```
Hola [primer_nombre],

Habla Jorge de Aremko. Espero que la espalda les haya quedado mejor de lo que llegó 😊

Una pregunta corta: ¿nos dejarían una reseña en Google? Toma 1 minuto y nos ayuda muchísimo a que más personas como ustedes encuentren Aremko.

Acá el link directo:
👉 https://g.page/r/CbKKwbV5UmD_EBM/review

Y si algo no fue lo esperado, contéstenme acá mismo. Nos importa más arreglarlo que recibir una reseña.

Gracias!
Jorge — Aremko Spa Boutique
```

### Variante corta (alternativa A/B)
```
[primer_nombre], ¿qué tal la tina?

Si les gustó, una reseña en Google nos cambia la semana → https://g.page/r/CbKKwbV5UmD_EBM/review

Toma 1 minuto. Y si algo no fue ideal, escríbeme acá.

Jorge — Aremko
```

---

## 📧 Email post-visita (HTML)

**Cuándo:** 48 horas después del checkout (después del WhatsApp, para quienes no respondieron)
**Quién recibe:** clientes con email y `permite_email=True` que NO dejaron reseña en las 24h post-WhatsApp
**Asunto:** `¿Cómo te fue, [primer_nombre]?`
**Asunto alternativo (A/B):** `Una reseña que te tomará 1 minuto`

### Cuerpo (HTML)

```html
<!DOCTYPE html>
<html>
<body style="font-family: Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333; line-height: 1.6;">

  <p>Hola [primer_nombre],</p>

  <p>Te escribo personalmente porque hace un par de días estuviste en Aremko y quería saber cómo te fue.</p>

  <p>Si la experiencia fue buena, te quería pedir un favor: <strong>déjanos una reseña en Google</strong>. Toma menos de 1 minuto y nos ayuda muchísimo. Las opiniones reales son lo que hace que más personas como tú encuentren Aremko.</p>

  <div style="text-align: center; margin: 30px 0;">
    <a href="https://g.page/r/CbKKwbV5UmD_EBM/review"
       style="background: #2c5f5d; color: #fff; padding: 14px 28px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 16px; display: inline-block;">
      Dejar mi reseña →
    </a>
  </div>

  <p style="color: #666; font-size: 14px;">Y si algo no fue lo esperado, <strong>contéstame este correo</strong>. Prefiero arreglar lo que falló antes de pedir una reseña. Tu opinión real (la buena y la incómoda) nos importa más que las estrellas.</p>

  <p>Gracias por elegirnos.</p>

  <p>
    Jorge<br>
    <strong>Aremko Spa Boutique</strong><br>
    Río Pescado · Puerto Varas<br>
    <a href="https://www.aremko.cl" style="color: #2c5f5d;">aremko.cl</a>
  </p>

  <hr style="border: none; border-top: 1px solid #e8e8e8; margin: 30px 0;">

  <p style="font-size: 12px; color: #888; text-align: center;">
    Si no quieres recibir más correos como este, <a href="{{ unsubscribe_url }}" style="color: #888;">desuscríbete acá</a>.
  </p>

</body>
</html>
```

### Cuerpo texto plano (fallback)

```
Hola [primer_nombre],

Te escribo personalmente porque hace un par de días estuviste en Aremko y quería saber cómo te fue.

Si la experiencia fue buena, te quería pedir un favor: déjanos una reseña en Google. Toma menos de 1 minuto y nos ayuda muchísimo. Las opiniones reales son lo que hace que más personas como tú encuentren Aremko.

Dejar mi reseña: https://g.page/r/CbKKwbV5UmD_EBM/review

Y si algo no fue lo esperado, contéstame este correo. Prefiero arreglar lo que falló antes de pedir una reseña. Tu opinión real (la buena y la incómoda) nos importa más que las estrellas.

Gracias por elegirnos.

Jorge
Aremko Spa Boutique
Río Pescado · Puerto Varas
aremko.cl

---
Si no quieres recibir más correos como este, desuscríbete acá: {{ unsubscribe_url }}
```

---

## ⚙️ Lógica de envío automático (a implementar)

Management command `send_review_request` que:

1. Busca clientes con `VentaReserva` que cumple:
   - `fecha_reserva` fue hace exactamente **1 día** (>=23h y <=25h, ventana de 2h)
   - `estado_pago` = `pagado` (o estado equivalente al checkout)
   - Cliente con `permite_sms=True` (para WhatsApp) o `permite_email=True` (para email)
   - Cliente NO ha recibido este request antes (campo `review_request_sent_at` que vamos a agregar al modelo Cliente — pero como dice CLAUDE.md, las migraciones las ejecuta Jorge manualmente desde Render shell, así que coordinamos eso)

2. Para cada cliente:
   - Si `permite_sms=True` y tiene teléfono: envía WhatsApp con plantilla corta (24h)
   - Si NO tiene WhatsApp habilitado pero tiene email: envía email (24h)
   - Marca `review_request_sent_at = now()` para no duplicar

3. Frecuencia del cron: 1 vez al día a las 11:00 AM hora Chile (cron-job.org)

### Pseudo-código del management command

```python
from datetime import timedelta
from django.utils import timezone
from ventas.models import VentaReserva, Cliente, CommunicationLog

def handle(self, *args, **options):
    yesterday = timezone.now() - timedelta(days=1)
    window_start = yesterday - timedelta(hours=1)
    window_end = yesterday + timedelta(hours=1)

    visits = VentaReserva.objects.filter(
        fecha_reserva__gte=window_start,
        fecha_reserva__lte=window_end,
        estado_pago='pagado',
    ).select_related('cliente')

    for visit in visits:
        cliente = visit.cliente
        if not cliente:
            continue
        if cliente.review_request_sent_at:  # ya recibió
            continue

        if cliente.permite_sms and cliente.telefono:
            send_whatsapp_review_request(cliente)
        elif cliente.permite_email and cliente.email:
            send_email_review_request(cliente)

        cliente.review_request_sent_at = timezone.now()
        cliente.save()
```

---

## 📊 Métricas a trackear

- Tasa de envío: cuántos clientes/visita reciben el request
- Tasa de apertura (email): SendGrid stats
- Tasa de clic en el link: GA4 con UTM `?utm_source=postvisita&utm_medium=whatsapp/email`
- **Tasa de conversión a reseña real**: comparando reseñas nuevas en Google Maps vs envíos hechos

Meta: 30-40% de los clientes que reciben mensaje dejan reseña → 6-12 reseñas/semana → 24-48 reseñas/mes → 80+ reseñas en 60 días.
