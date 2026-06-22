# -*- coding: utf-8 -*-
"""Previsualiza el briefing de Luna Interna para un número, sin enviar nada.

Sirve para validar el CONTENIDO del briefing (pagos/saldos/tareas/comandas) antes
de conectar el envío por WhatsApp. Tal cual lo recibirá el trabajador.

Uso:
    python manage.py preview_briefing --telefono +56912345678
    python manage.py preview_briefing            # lista el personal cargado
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Previsualiza el briefing de un número del personal (no envía nada)."

    def add_arguments(self, parser):
        parser.add_argument('--telefono', type=str, default='',
                            help='Número a previsualizar (E.164 o con los últimos 9 dígitos).')

    def handle(self, *args, **options):
        from personal_operativo.models import PersonalOperativo
        from personal_operativo.services import buscar_personal, construir_briefing

        tel = options['telefono'].strip()
        if not tel:
            self.stdout.write('Personal operativo cargado:')
            for p in PersonalOperativo.objects.all():
                auto = 'AUTO' if p.responde_auto else 'borrador'
                act = 'activo' if p.activo else 'inactivo'
                self.stdout.write(f'  • {p.nombre} | {p.telefono} | {p.get_rol_display()} | {auto} | {act}')
            self.stdout.write('\nUsa --telefono <número> para ver su briefing.')
            return

        persona = buscar_personal(tel)
        if not persona:
            self.stdout.write(self.style.ERROR(
                f'El número {tel} NO está en la whitelist (PersonalOperativo) o está inactivo. '
                f'Agrégalo en el admin → "Personal Operativo (Luna Interna)".'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'Identificado: {persona.nombre} ({persona.get_rol_display()}) · '
            f'responde_auto={persona.responde_auto}\n'))
        self.stdout.write('─' * 50)
        self.stdout.write(construir_briefing(persona))
        self.stdout.write('─' * 50)
