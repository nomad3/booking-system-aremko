# -*- coding: utf-8 -*-
"""Lo que el dueño decide una vez y el resumen diario le repite.

El problema que resuelve esta app no es falta de información: es que la
información espera a que uno vaya a buscarla, y entre tres negocios se pierde
el hilo. Acá viven las dos cosas que ningún sistema puede calcular solo —
cuáles son las prioridades de la semana y cómo va un negocio que todavía no
tiene datos automáticos.
"""
from django.db import models

NEGOCIOS = [
    ('aremko', 'Aremko'),
    ('datamatic', 'Datamatic'),
    ('torqueria', 'Torquería'),
]


class PrioridadSemana(models.Model):
    """Las pocas cosas que importan esta semana.

    Se fijan una vez (el lunes) y el resumen las repite cada mañana. Sin esto
    el correo sería un muro de números más: saber cómo va el negocio no es lo
    mismo que acordarse de qué se decidió hacer con él.
    """

    semana_inicio = models.DateField(
        'semana (lunes)', db_index=True,
        help_text='El lunes de la semana a la que pertenece. '
                  'Se muestran las de la semana en curso.')
    negocio = models.CharField(max_length=20, choices=NEGOCIOS, default='aremko')
    orden = models.PositiveSmallIntegerField(
        default=1, help_text='1, 2, 3… El orden en que las quieres leer.')
    texto = models.CharField(max_length=200)
    hecha = models.BooleanField(
        'lista', default=False,
        help_text='Marcada, deja de aparecer como pendiente en el resumen.')
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Prioridad de la semana'
        verbose_name_plural = 'Prioridades de la semana'
        # Sin restricción de unicidad a propósito: dos prioridades con el
        # mismo número se ordenan por id y se muestran igual. Un error de
        # tipeo no debe dejar a nadie trancado un lunes a las 7 de la mañana.
        ordering = ['negocio', 'orden', 'id']

    def __str__(self):
        return f'{self.get_negocio_display()} · {self.orden}. {self.texto[:60]}'


class NotaNegocio(models.Model):
    """El estado de un negocio en una línea, escrita a mano.

    Torquería y Datamatic todavía no tienen datos automáticos en este sistema.
    Antes que inventar métricas o dejar el bloque vacío, se muestra lo que el
    dueño escribió y CUÁNDO lo escribió: una nota de hace tres semanas se lee
    distinto que una de ayer.
    """

    negocio = models.CharField(max_length=20, choices=NEGOCIOS, unique=True)
    texto = models.CharField(max_length=300)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Nota de negocio'
        verbose_name_plural = 'Notas de negocios'
        ordering = ['negocio']

    def __str__(self):
        return f'{self.get_negocio_display()}: {self.texto[:60]}'
