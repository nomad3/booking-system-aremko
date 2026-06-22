# -*- coding: utf-8 -*-
"""Identidad del staff de Aremko para "Luna Interna" (ver docs/PLAN_LUNA_INTERNA.md).

Esta tabla ES LA WHITELIST: mapea el número de WhatsApp del que escribe → su
identidad (usuario, rol, turno) y el interruptor de autonomía (`responde_auto`).

Principio (Fase 1 del plan): el staff es un conjunto finito y conocido, así que a
estos números Luna les puede responder AUTOMÁTICAMENTE (sin la aprobación de
Deborah que sí aplica a clientes). Una sola pregunta — "¿este número está acá,
activo y con responde_auto?" — decide el modo de operación.

Para masajistas no se duplica nada: vía `usuario` se llega a su `Proveedor`
(OneToOne `Proveedor.usuario`) y de ahí a sus horarios/fichas.
"""
from django.conf import settings
from django.db import models


class PersonalOperativo(models.Model):
    ROLES = [
        ('jefatura', 'Jefatura / Administración'),
        ('recepcion', 'Recepción'),
        ('masajista', 'Masajista'),
        ('mantencion', 'Mantención'),
        ('otro', 'Otro'),
    ]
    TURNOS = [
        ('manana', 'Mañana'),
        ('tarde', 'Tarde'),
        ('completo', 'Completo / Variable'),
    ]

    nombre = models.CharField(max_length=120)
    telefono = models.CharField(
        max_length=20, unique=True, db_index=True,
        help_text='Número del trabajador en formato E.164 (+56...). Es la LLAVE de la whitelist: '
                  'el número desde el que escribe al WhatsApp de Aremko.')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='personal_operativo',
        help_text='Usuario del sistema (para resolver sus tareas y rol). Si es masajista, desde '
                  'el usuario se llega a su Proveedor (usuario.proveedor).')
    rol = models.CharField(max_length=20, choices=ROLES, default='otro')
    turno = models.CharField(max_length=12, choices=TURNOS, default='completo', blank=True)

    responde_auto = models.BooleanField(
        default=False,
        help_text='⚙️ INTERRUPTOR DE AUTONOMÍA: si está activo, Luna le responde AUTOMÁTICAMENTE '
                  '(sin pasar por la aprobación de Deborah). Solo para staff de confianza.')
    activo = models.BooleanField(default=True)
    notas = models.TextField(blank=True, default='')

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Personal operativo'
        verbose_name_plural = 'Personal Operativo (Luna Interna)'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.get_rol_display()})'

    @property
    def proveedor(self):
        """Devuelve el Proveedor del masajista vía su usuario, o None."""
        u = self.usuario
        if not u:
            return None
        return getattr(u, 'proveedor', None)
