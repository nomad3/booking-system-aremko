# -*- coding: utf-8 -*-
"""Crea el grupo «Finanzas colaborador» y mete al usuario EXISTENTE de Alda
(2026-08-09, dato de Jorge: ella ya tiene usuario y conserva su contraseña).

    python manage.py configurar_acceso_alda              # busca su usuario solo
    python manage.py configurar_acceso_alda --usuario X  # si hay que precisar

Idempotente. Nunca toca contraseñas.
"""
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db.models import Q

GRUPO = 'Finanzas colaborador'


class Command(BaseCommand):
    help = 'Grupo Finanzas colaborador + el usuario existente de Alda adentro.'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', default='',
                            help='Username exacto si la búsqueda no lo encuentra sola.')

    def handle(self, *args, **opts):
        grupo, creado_g = Group.objects.get_or_create(name=GRUPO)
        self.stdout.write(f'Grupo «{GRUPO}»: {"creado" if creado_g else "ya existía"}')

        if opts['usuario']:
            candidatos = list(User.objects.filter(username=opts['usuario']))
        else:
            candidatos = list(User.objects.filter(
                Q(username__icontains='alda') | Q(username__icontains='angelica')
                | Q(first_name__icontains='alda') | Q(first_name__icontains='angelica')
                | Q(last_name__icontains='toloza')))

        if len(candidatos) != 1:
            self.stdout.write(self.style.WARNING(
                f'{len(candidatos)} usuarios candidatos — precisar con '
                f'--usuario <username>. Encontrados:'))
            for u in candidatos or User.objects.filter(is_active=True)[:15]:
                self.stdout.write(f'  {u.username} · {u.get_full_name() or "(sin nombre)"} '
                                  f'· staff={u.is_staff}')
            return

        usuario = candidatos[0]
        if not usuario.is_staff:
            usuario.is_staff = True
            usuario.save(update_fields=['is_staff'])
        usuario.groups.add(grupo)
        self.stdout.write(self.style.SUCCESS(
            f'Listo: {usuario.username} ({usuario.get_full_name() or "sin nombre"}) '
            f'quedó en «{GRUPO}» · staff ✓ · su contraseña quedó INTACTA.'))
