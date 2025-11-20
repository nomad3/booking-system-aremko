"""
Script para crear GiftCards de packs especiales
Ejecutar con: python manage.py shell < crear_giftcards_pack.py
"""
from ventas.models import GiftCard, Cliente
from datetime import datetime, timedelta
from django.utils import timezone
import random
import string

def generar_codigo_giftcard():
    """Genera un código único de 12 caracteres"""
    while True:
        codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        if not GiftCard.objects.filter(codigo=codigo).exists():
            return codigo

# Buscar o crear cliente Aremko para las GiftCards
cliente_aremko, created = Cliente.objects.get_or_create(
    email='info@aremko.cl',
    defaults={
        'nombre': 'Aremko',
        'telefono': '+56912345678',  # Ajustar al teléfono real
        'pais': 'Chile',
        'ciudad': 'Puerto Varas'
    }
)

if created:
    print(f"✅ Cliente Aremko creado: {cliente_aremko.nombre}")
else:
    print(f"ℹ️ Cliente Aremko ya existe: {cliente_aremko.nombre}")

# Fecha de vencimiento: 1 año desde hoy
fecha_vencimiento = timezone.now().date() + timedelta(days=365)

# GiftCard #1: Pack 4 Personas - $190,000
giftcard_4p = GiftCard.objects.create(
    codigo=generar_codigo_giftcard(),
    monto_inicial=190000,
    monto_disponible=190000,
    fecha_emision=timezone.now().date(),
    fecha_vencimiento=fecha_vencimiento,
    estado='por_cobrar',
    cliente_comprador=cliente_aremko,
    comprador_nombre='Aremko',
    comprador_email='info@aremko.cl',
    destinatario_nombre='Destinatario Gift Card 4 Personas',
    destinatario_email='',
    servicio_asociado='4 horas tinas + masaje para 4 personas',
    detalle_especial='Gift Card válida para 4 personas: 4 horas de tinas + masaje para 4',
    tipo_mensaje='regalo',
    mensaje_personalizado='Disfruta de una experiencia única para 4 personas con tinas y masajes.',
    enviado_email=False,
    enviado_whatsapp=False
)

print(f"\n✅ GiftCard 4 Personas creada:")
print(f"   Código: {giftcard_4p.codigo}")
print(f"   Monto: ${giftcard_4p.monto_inicial:,.0f}")
print(f"   Vencimiento: {giftcard_4p.fecha_vencimiento}")

# GiftCard #2: Pack 6 Personas - $285,000
giftcard_6p = GiftCard.objects.create(
    codigo=generar_codigo_giftcard(),
    monto_inicial=285000,
    monto_disponible=285000,
    fecha_emision=timezone.now().date(),
    fecha_vencimiento=fecha_vencimiento,
    estado='por_cobrar',
    cliente_comprador=cliente_aremko,
    comprador_nombre='Aremko',
    comprador_email='info@aremko.cl',
    destinatario_nombre='Destinatario Gift Card 6 Personas',
    destinatario_email='',
    servicio_asociado='4 horas tinas + masaje para 6 personas',
    detalle_especial='Gift Card válida para 6 personas: 4 horas de tinas + masaje para 6',
    tipo_mensaje='regalo',
    mensaje_personalizado='Disfruta de una experiencia única para 6 personas con tinas y masajes.',
    enviado_email=False,
    enviado_whatsapp=False
)

print(f"\n✅ GiftCard 6 Personas creada:")
print(f"   Código: {giftcard_6p.codigo}")
print(f"   Monto: ${giftcard_6p.monto_inicial:,.0f}")
print(f"   Vencimiento: {giftcard_6p.fecha_vencimiento}")

print(f"\n🎉 GiftCards creadas exitosamente!")
print(f"\nTotal GiftCards en el sistema: {GiftCard.objects.count()}")
