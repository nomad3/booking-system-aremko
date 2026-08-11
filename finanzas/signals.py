# -*- coding: utf-8 -*-
"""Una sola señal: mantener al día el caché de las reglas de glosa.

Sin esto, una regla nueva no regiría hasta el próximo reinicio del servidor —
y Jorge la crearía justo antes de subir la cartola donde la necesita.
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import ReglaGlosa
from .reglas_glosa import invalidar_cache


@receiver(post_save, sender=ReglaGlosa)
@receiver(post_delete, sender=ReglaGlosa)
def _botar_cache(sender, **kwargs):
    invalidar_cache()
