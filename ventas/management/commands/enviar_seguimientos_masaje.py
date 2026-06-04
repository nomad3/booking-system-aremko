"""
enviar_seguimientos_masaje
==========================

Envía los emails de seguimiento de bienestar (Conexión-Masajes, F6) que ya
vencieron y están pendientes.

SEGURIDAD: apagado por defecto. Solo envía si settings.MASAJE_SEGUIMIENTOS_ACTIVOS
= True (env var MASAJE_SEGUIMIENTOS_ACTIVOS=true). Mientras esté apagado, solo
informa cuántos hay pendientes (no manda nada a clientes reales).

Pensado para correr a diario (queda enganchado a send_communication_triggers
type=all). También se puede correr suelto:

    python manage.py enviar_seguimientos_masaje
"""

from django.core.management.base import BaseCommand

from ventas.services.masaje_seguimiento_service import procesar_seguimientos_pendientes


class Command(BaseCommand):
    help = "Envía los seguimientos de bienestar de masaje vencidos (si están activados)."

    def handle(self, *args, **opts):
        r = procesar_seguimientos_pendientes()
        if not r.get('activo'):
            self.stdout.write(self.style.WARNING(
                f"Seguimientos de masaje DESACTIVADOS (MASAJE_SEGUIMIENTOS_ACTIVOS=False). "
                f"Pendientes vencidos en cola: {r.get('pendientes_vencidos', 0)}."
            ))
            return
        self.stdout.write(self.style.SUCCESS(
            f"✓ Seguimientos de masaje: {r['enviados']} enviado(s), {r['errores']} error(es)."
        ))
