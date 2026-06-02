"""Crea/actualiza los grupos de acceso de Conexión-Masajes:

- 'Masajistas': acceso SOLO a la Ficha de Bienestar (ver + editar). Pensado para
  que cada masajista (con su usuario+contraseña, is_staff=True) complete únicamente
  el resumen del terapeuta. No ve reservas, pagos ni clientes.
- 'Coordinacion Masajes': acceso de coordinación (Deborah) — reservas, participantes,
  fichas y seguimientos.

Uso: python manage.py setup_masajistas
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = "Crea/actualiza los grupos 'Masajistas' y 'Coordinacion Masajes'."

    def _perms(self, model, acciones):
        from ventas import models as m
        ct = ContentType.objects.get_for_model(getattr(m, model))
        codenames = [f"{a}_{getattr(m, model)._meta.model_name}" for a in acciones]
        return list(Permission.objects.filter(content_type=ct, codename__in=codenames))

    def handle(self, *args, **opts):
        # Grupo Masajistas: SOLO ficha (ver + cambiar)
        g_mas, _ = Group.objects.get_or_create(name='Masajistas')
        perms_mas = self._perms('BienestarMasajeFicha', ['view', 'change'])
        g_mas.permissions.set(perms_mas)
        self.stdout.write(self.style.SUCCESS(
            f"Grupo 'Masajistas' listo ({len(perms_mas)} permisos: ver+editar Ficha de Bienestar)."
        ))

        # Grupo Coordinacion Masajes (Deborah): reservas + participantes + fichas + seguimientos
        g_coord, _ = Group.objects.get_or_create(name='Coordinacion Masajes')
        perms_coord = []
        perms_coord += self._perms('BienestarMasajeFicha', ['view', 'add', 'change'])
        perms_coord += self._perms('ParticipanteMasajeReserva', ['view', 'add', 'change'])
        perms_coord += self._perms('SeguimientoBienestarMasaje', ['view', 'change'])
        perms_coord += self._perms('VentaReserva', ['view', 'change'])
        perms_coord += self._perms('Cliente', ['view'])
        g_coord.permissions.set(perms_coord)
        self.stdout.write(self.style.SUCCESS(
            f"Grupo 'Coordinacion Masajes' listo ({len(perms_coord)} permisos)."
        ))

        self.stdout.write("")
        self.stdout.write("Siguiente paso: en el admin → Usuarios, crea cada masajista con")
        self.stdout.write("is_staff=True, asígnale el grupo 'Masajistas' y una contraseña.")
