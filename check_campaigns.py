#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para ver campañas de EmailCampaign activas
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import EmailCampaign, EmailRecipient

print("\n" + "="*60)
print("CAMPAÑAS DE EMAIL ACTIVAS")
print("="*60)

campaigns = EmailCampaign.objects.all().order_by('-created_at')[:10]

if not campaigns:
    print("\n❌ No hay campañas registradas")
else:
    for c in campaigns:
        print(f"\n📧 ID: {c.id} | {c.name}")
        print(f"   Estado: {c.status}")
        print(f"   Creada: {c.created_at.strftime('%Y-%m-%d %H:%M')}")

        # Contar recipients
        total = EmailRecipient.objects.filter(campaign=c).count()
        pending = EmailRecipient.objects.filter(campaign=c, status='pending', send_enabled=True).count()
        sent = EmailRecipient.objects.filter(campaign=c, status__in=['sent', 'delivered']).count()

        print(f"   Total destinatarios: {total}")
        print(f"   Pendientes: {pending}")
        print(f"   Enviados: {sent}")
        print(f"   Progreso: {(sent/total*100) if total > 0 else 0:.1f}%")

print("\n" + "="*60)
print()
