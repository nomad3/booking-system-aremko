#!/usr/bin/env python3
"""
Script para resolver problema de campaña con email inválido que sigue intentando enviar.
Ejecutar desde Render: python scripts/fix_campaign_with_invalid_email.py
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')

import django
django.setup()

from ventas.models import EmailCampaign, EmailRecipient, Cliente
from django.utils import timezone

print("\n" + "=" * 80)
print("FIX CAMPAÑA CON EMAIL INVÁLIDO")
print("=" * 80)

# Buscar la campaña problemática
print("\n🔍 Buscando campaña 'de 50.000 a 60.000 giftcards'...")
print("-" * 80)

try:
    campaign = EmailCampaign.objects.get(name__icontains="50.000 a 60.000")
    print(f"✅ Campaña encontrada: {campaign.name}")
    print(f"   ID: {campaign.id}")
    print(f"   Estado: {campaign.status} ({campaign.get_status_display()})")
    print(f"   Total destinatarios: {campaign.total_recipients}")
    print(f"   Emails enviados: {campaign.emails_sent}")
    print(f"   Progreso: {campaign.progress_percentage:.1f}%")
except EmailCampaign.DoesNotExist:
    print("❌ ERROR: No se encontró la campaña")
    print("\nBuscando todas las campañas activas...")
    campaigns = EmailCampaign.objects.exclude(status__in=['completed', 'cancelled'])
    for c in campaigns:
        print(f"   - {c.name} ({c.status})")
    sys.exit(1)

# Buscar el destinatario problemático
print("\n🔍 Buscando destinatario con email inválido...")
print("-" * 80)

recipients_pending = EmailRecipient.objects.filter(
    campaign=campaign,
    status='pending'
)

print(f"📊 Destinatarios pendientes: {recipients_pending.count()}")

# Buscar el que tenga error
problema_encontrado = False
for recipient in recipients_pending:
    print(f"\n   Cliente: {recipient.name}")
    print(f"   Email: {recipient.email}")
    print(f"   Estado: {recipient.status}")

    if recipient.error_message:
        print(f"   ⚠️  Error: {recipient.error_message}")

    # Verificar si el email parece inválido (es un nombre en vez de email)
    if '@' not in recipient.email:
        print(f"   ❌ EMAIL INVÁLIDO: No contiene '@'")
        problema_encontrado = True
        problema_recipient = recipient

if not problema_encontrado:
    print("\n⚠️  No se encontró el destinatario con error obvio")
    print("Mostrando todos los destinatarios pendientes:")
    for r in recipients_pending:
        print(f"   - {r.name} ({r.email})")

# ==============================================================================
# OPCIONES DE SOLUCIÓN
# ==============================================================================
print("\n\n" + "=" * 80)
print("OPCIONES PARA RESOLVER EL PROBLEMA")
print("=" * 80)

print("\nOPCIÓN 1: Marcar destinatario específico como 'excluded'")
print("   ✅ Pros: Solo afecta al destinatario problemático")
print("   ✅ Pros: La campaña puede continuar con otros destinatarios si los hay")
print("   ⚠️  Contras: El destinatario quedará en la base de datos")

print("\nOPCIÓN 2: Eliminar destinatario problemático")
print("   ✅ Pros: Limpia completamente el problema")
print("   ⚠️  Contras: Se pierde el registro del intento")

print("\nOPCIÓN 3: Marcar toda la campaña como 'completed'")
print("   ✅ Pros: Detiene todos los intentos de envío")
print("   ✅ Pros: Mantiene todos los registros")
print("   ⚠️  Contras: Si hay otros destinatarios pendientes válidos, no se enviarán")

print("\nOPCIÓN 4: Marcar toda la campaña como 'cancelled'")
print("   ✅ Pros: Detiene todos los intentos de envío")
print("   ✅ Pros: Mantiene todos los registros")
print("   ℹ️  Info: Similar a opción 3, pero más claro que fue cancelada manualmente")

print("\n" + "-" * 80)
print("RECOMENDACIÓN:")
if recipients_pending.count() == 1 and problema_encontrado:
    print("   Como solo hay 1 destinatario pendiente y tiene un email inválido,")
    print("   la OPCIÓN 1 (marcar como excluded) es la más limpia.")
    print("   Esto detendrá los intentos de reenvío sin afectar las estadísticas.")
else:
    print("   Revisar cuántos destinatarios pendientes válidos hay antes de decidir.")

# ==============================================================================
# APLICAR FIX
# ==============================================================================
print("\n\n" + "=" * 80)
print("¿QUÉ DESEAS HACER?")
print("=" * 80)
print("\n1. Marcar destinatario problemático como 'excluded' (RECOMENDADO)")
print("2. Eliminar destinatario problemático")
print("3. Marcar campaña completa como 'completed'")
print("4. Marcar campaña completa como 'cancelled'")
print("5. Solo ver información, no hacer cambios")
print()

opcion = input("Ingresa el número de la opción (1-5): ").strip()

if opcion == "1":
    print("\n🔧 Aplicando OPCIÓN 1: Marcar como 'excluded'...")
    print("-" * 80)

    if problema_encontrado:
        problema_recipient.status = 'excluded'
        problema_recipient.error_message = "Email inválido - marcado como excluded manualmente"
        problema_recipient.send_enabled = False
        problema_recipient.save()

        print(f"✅ Destinatario marcado como 'excluded':")
        print(f"   Nombre: {problema_recipient.name}")
        print(f"   Email: {problema_recipient.email}")
        print(f"   Nuevo estado: {problema_recipient.status}")
        print(f"   Send enabled: {problema_recipient.send_enabled}")

        # Verificar si quedan destinatarios pendientes
        pendientes_restantes = EmailRecipient.objects.filter(
            campaign=campaign,
            status='pending'
        ).count()

        print(f"\n📊 Destinatarios pendientes restantes: {pendientes_restantes}")

        if pendientes_restantes == 0:
            print("\n💡 SUGERENCIA: Como no quedan destinatarios pendientes,")
            print("   podrías marcar la campaña como 'completed'.")
            completar = input("\n¿Marcar campaña como completed? (s/n): ").strip().lower()
            if completar in ['s', 'si', 'sí', 'y', 'yes']:
                campaign.status = 'completed'
                campaign.save()
                print(f"✅ Campaña marcada como 'completed'")
    else:
        print("❌ No se pudo identificar el destinatario problemático")

elif opcion == "2":
    print("\n🔧 Aplicando OPCIÓN 2: Eliminar destinatario...")
    print("-" * 80)

    if problema_encontrado:
        nombre = problema_recipient.name
        email = problema_recipient.email

        confirmar = input(f"⚠️  ¿CONFIRMAS eliminar a '{nombre}' ({email})? (escribe 'ELIMINAR'): ")
        if confirmar == 'ELIMINAR':
            problema_recipient.delete()
            print(f"✅ Destinatario eliminado")

            # Actualizar contador de la campaña
            campaign.total_recipients = EmailRecipient.objects.filter(campaign=campaign).count()
            campaign.save()
            print(f"✅ Total de destinatarios actualizado: {campaign.total_recipients}")
        else:
            print("❌ Eliminación cancelada")
    else:
        print("❌ No se pudo identificar el destinatario problemático")

elif opcion == "3":
    print("\n🔧 Aplicando OPCIÓN 3: Marcar campaña como 'completed'...")
    print("-" * 80)

    confirmar = input(f"⚠️  ¿CONFIRMAS marcar '{campaign.name}' como completed? (s/n): ")
    if confirmar.lower() in ['s', 'si', 'sí', 'y', 'yes']:
        campaign.status = 'completed'
        campaign.save()
        print(f"✅ Campaña marcada como 'completed'")
        print(f"   Esto detendrá todos los intentos de envío automático")
    else:
        print("❌ Operación cancelada")

elif opcion == "4":
    print("\n🔧 Aplicando OPCIÓN 4: Marcar campaña como 'cancelled'...")
    print("-" * 80)

    confirmar = input(f"⚠️  ¿CONFIRMAS marcar '{campaign.name}' como cancelled? (s/n): ")
    if confirmar.lower() in ['s', 'si', 'sí', 'y', 'yes']:
        campaign.status = 'cancelled'
        campaign.save()
        print(f"✅ Campaña marcada como 'cancelled'")
        print(f"   Esto detendrá todos los intentos de envío automático")
    else:
        print("❌ Operación cancelada")

elif opcion == "5":
    print("\n✅ Solo se mostró información, no se hicieron cambios")

else:
    print("\n❌ Opción inválida, no se hicieron cambios")

print("\n" + "=" * 80)
print("FIN DEL SCRIPT")
print("=" * 80 + "\n")
