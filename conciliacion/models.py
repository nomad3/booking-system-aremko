"""Modelos de conciliación bancaria (AP-001 · Tier-2 para AgentProvision).

App AISLADA (drift-safe, igual que whatsapp_agent/carrito_reservas/inbox_omnicanal):
no toca los modelos de `ventas` para no chocar con el drift AR-033/AR-034.

Diseño LEAN (decisión de Jorge 2026-06-30): los MOVIMIENTOS bancarios viven en
AgentProvision (el cerebro que los lee de Gmail). Django solo guarda el REGISTRO
AUDITADO de cada pago conciliado que se aplicó, con su clave de idempotencia.
"""

from django.db import models


class ReconciliacionLog(models.Model):
    """Una fila por cada pago conciliado que AgentProvision aplicó a una reserva.

    Sirve para dos cosas:
      1. **Idempotencia:** `referencia` (id único del movimiento bancario/MP que mandó
         AgentProvision) es UNIQUE → el mismo movimiento no puede aplicarse dos veces.
      2. **Auditoría:** quién (`actor`), cuándo (`creado_en`), cuánto (`monto`/`metodo_pago`),
         de qué fuente (`origen`), contra qué reserva/pago, y el `payload` crudo recibido.

    Solo se crea cuando el pago se aplicó OK (dentro de la misma transacción que el `Pago`).
    Si la aplicación falla, la transacción hace rollback y NO queda fila → se puede reintentar.
    """

    ESTADOS = [
        ('aplicado', 'Aplicado'),
        ('reversado', 'Reversado'),  # para anulaciones futuras; hoy siempre se crea 'aplicado'
    ]

    referencia = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text='ID único del movimiento (operación MP, hash de transferencia, etc.). '
                  'Clave de idempotencia: el mismo movimiento no se aplica dos veces.',
    )
    reserva = models.ForeignKey(
        'ventas.VentaReserva',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reconciliaciones',
        help_text='Reserva a la que se aplicó el pago (SET_NULL para preservar el log).',
    )
    pago = models.ForeignKey(
        'ventas.Pago',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reconciliaciones',
        help_text='Pago creado al aplicar la conciliación.',
    )
    monto = models.DecimalField(
        max_digits=10, decimal_places=0,
        help_text='Monto aplicado (snapshot, por si el Pago se borra).',
    )
    metodo_pago = models.CharField(
        max_length=100,
        help_text='Método con que se registró el Pago (ej. transferencia, mercadopago).',
    )
    origen = models.CharField(
        max_length=50, default='gmail',
        help_text='De dónde leyó AgentProvision el movimiento (gmail, mercadopago, manual…).',
    )
    actor = models.CharField(
        max_length=100, default='agentprovision',
        help_text='Quién aplicó la conciliación (agente o usuario).',
    )
    fecha_movimiento = models.DateTimeField(
        null=True, blank=True,
        help_text='Fecha real del movimiento bancario (de la fuente), distinta de creado_en.',
    )
    payload = models.JSONField(
        default=dict, blank=True,
        help_text='Datos crudos del movimiento que mandó AgentProvision (auditoría).',
    )
    estado = models.CharField(
        max_length=20, choices=ESTADOS, default='aplicado', db_index=True,
    )
    notas = models.TextField(blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'conciliacion_reconciliacionlog'
        verbose_name = 'Log de conciliación'
        verbose_name_plural = 'Logs de conciliación'
        ordering = ['-creado_en']
        # NB: 'reserva' y 'pago' (FK) ya se indexan solos; solo declaramos los no-FK.
        indexes = [
            models.Index(fields=['origen'], name='recon_origen_idx'),
        ]

    def __str__(self):
        return f'Recon {self.referencia} → reserva {self.reserva_id} (${self.monto})'
