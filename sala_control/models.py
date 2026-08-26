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


class MarcaPublicacion(models.Model):
    """«De esta ya me hice cargo», dicho por el dueño en su panel.

    El estado real de una pieza vive en el Telar y llega solo desde allá. Esta
    marca es aparte y es del dueño: le sirve para despejar su lista del día sin
    esperar a que alguien marque en Datamatic. Una fila se considera resuelta
    si el Telar dice «publicada» O si existe esta marca — nunca compiten dos
    verdades sobre lo mismo, porque responden preguntas distintas: allá «¿se
    publicó?», acá «¿ya lo revisé?».
    """

    fecha = models.DateField(db_index=True)
    publicacion_id = models.PositiveIntegerField(
        help_text='Id de la pieza en el Telar (Datamatic). Llave estable: el '
                  'título se edita y la hora se mueve.')
    titulo = models.CharField(
        max_length=200, blank=True, default='',
        help_text='Copia de cortesía para poder leer el historial sin ir al Telar.')
    marcada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Publicación marcada'
        verbose_name_plural = 'Publicaciones marcadas'
        ordering = ['-fecha', '-id']
        constraints = [
            models.UniqueConstraint(fields=['fecha', 'publicacion_id'],
                                    name='marca_unica_por_pieza_y_dia'),
        ]

    def __str__(self):
        return f'{self.fecha:%d-%m} · pieza {self.publicacion_id}'


class NotaDelDia(models.Model):
    """Lo que aparece durante el día y hay que resolver o recordar.

    El resumen de la mañana no puede saber lo que va a pasar a las once. Acá el
    dueño agrega lo que le va cayendo —un pendiente, un link, algo que anotar—
    y lo despeja cuando está listo, sin salir del panel.
    """

    fecha = models.DateField(db_index=True)
    texto = models.CharField(max_length=300)
    link = models.URLField(
        blank=True, default='',
        help_text='Opcional: el correo, el panel o el documento del que se trata.')
    negocio = models.CharField(max_length=20, choices=NEGOCIOS, default='aremko')
    hecha = models.BooleanField(default=False)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Nota del día'
        verbose_name_plural = 'Notas del día'
        ordering = ['hecha', 'id']

    def __str__(self):
        return f'{self.fecha:%d-%m} · {self.texto[:60]}'


class CorteAds(models.Model):
    """La foto del gasto en publicidad, con la hora en que se tomó.

    Meta y Google son llamadas de red que demoran segundos. Un panel que se
    refresca solo no puede pedirlas cada vez: se arrastraría y quemaría cuota.
    Entonces el gasto se congela cuando corre el resumen de la mañana y el
    panel lo muestra CON SU HORA, que es lo que lo hace honesto — un número de
    publicidad sin hora se lee como si fuera de este minuto.
    """

    fecha = models.DateField(unique=True)
    meta = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True,
                               help_text='Vacío = no se pudo leer, que no es lo mismo que cero.')
    google = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    dias_ventana = models.PositiveSmallIntegerField(default=0)
    calculado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Corte de publicidad'
        verbose_name_plural = 'Cortes de publicidad'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.fecha:%d-%m} · Meta {self.meta} · Google {self.google}'

    @property
    def total(self):
        if self.meta is None and self.google is None:
            return None
        return int(self.meta or 0) + int(self.google or 0)
