# -*- coding: utf-8 -*-
"""
Comando para probar el servicio de IA de variación de contenido
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
import json

from ventas.services.ai_service import test_ai_service, ai_service


class Command(BaseCommand):
    help = 'Prueba el servicio de IA para variación de contenido de emails'

    def add_arguments(self, parser):
        parser.add_argument(
            '--subject',
            type=str,
            default="🎁 ¡Tu giftcard de $15,000 te espera en Aremko!",
            help='Asunto de prueba para generar variaciones'
        )
        parser.add_argument(
            '--count',
            type=int,
            default=3,
            help='Número de variaciones a generar'
        )
        parser.add_argument(
            '--body',
            type=str,
            default="Hola {nombre_cliente}, tenemos una sorpresa especial para ti en Aremko. ¡Ven a visitarnos!",
            help='Cuerpo de prueba para variación'
        )
        parser.add_argument(
            '--client-name',
            type=str,
            default="María González",
            help='Nombre de cliente para personalización'
        )

    def handle(self, *args, **options):
        self.stdout.write("\n" + "="*60)
        self.stdout.write("🤖 PRUEBA DEL SERVICIO DE IA - DEEPSEEK")
        self.stdout.write("="*60)
        
        # Mostrar configuración
        status = ai_service.get_status()
        self.stdout.write(f"\n📊 ESTADO DEL SERVICIO:")
        self.stdout.write(f"   ✅ Habilitado: {status['enabled']}")
        self.stdout.write(f"   🔧 Proveedor: {status['provider']}")
        self.stdout.write(f"   🤖 Modelo: {status['model']}")
        self.stdout.write(f"   🔑 API Key: {'✅ Configurada' if status['api_key_configured'] else '❌ Faltante'}")
        
        if not status['enabled'] or not status['api_key_configured']:
            self.stdout.write(self.style.ERROR("\n❌ Servicio de IA no está configurado correctamente."))
            self.stdout.write("   Verifica las variables de entorno DEEPSEEK_API_KEY y AI_VARIATION_ENABLED")
            return
        
        # Ejecutar pruebas
        self.stdout.write(f"\n🎯 EJECUTANDO PRUEBAS...")
        
        try:
            # Prueba 1: Variaciones de asunto
            self.stdout.write(f"\n1️⃣ GENERANDO VARIACIONES DE ASUNTO:")
            self.stdout.write(f"   📝 Original: {options['subject']}")
            
            subject_variations = ai_service.generate_subject_variations(
                options['subject'], 
                options['count']
            )
            
            for i, variation in enumerate(subject_variations, 1):
                self.stdout.write(f"   {i}️⃣ Variación: {variation}")
            
            # Prueba 2: Variación de cuerpo
            self.stdout.write(f"\n2️⃣ GENERANDO VARIACIÓN DE CUERPO:")
            self.stdout.write(f"   📝 Original: {options['body']}")
            self.stdout.write(f"   👤 Cliente: {options['client_name']}")
            
            body_variation = ai_service.generate_body_variations(
                options['body'],
                options['client_name']
            )
            
            self.stdout.write(f"   ✨ Variación: {body_variation}")
            
            # Prueba 3: Técnicas anti-spam
            self.stdout.write(f"\n3️⃣ APLICANDO TÉCNICAS ANTI-SPAM:")
            
            anti_spam_content = ai_service.apply_anti_spam_techniques(body_variation)
            self.stdout.write(f"   🛡️ Procesado: {anti_spam_content}")
            
            # Prueba 4: Función completa integrada
            self.stdout.write(f"\n4️⃣ PRUEBA INTEGRADA:")
            
            from ventas.services.ai_service import generate_personalized_content
            
            final_subject, final_body = generate_personalized_content(
                options['subject'],
                options['body'],
                options['client_name']
            )
            
            self.stdout.write(f"   📧 Asunto final: {final_subject}")
            self.stdout.write(f"   📄 Cuerpo final: {final_body}")
            
            # Estadísticas
            self.stdout.write(f"\n📊 ESTADÍSTICAS:")
            cache_stats = status.get('cache_stats', {})
            self.stdout.write(f"   💾 Variaciones en cache: {cache_stats}")
            
            self.stdout.write(self.style.SUCCESS(f"\n✅ ¡TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE!"))
            self.stdout.write("   El servicio de IA está funcionando correctamente.")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ ERROR EN LAS PRUEBAS: {str(e)}"))
            self.stdout.write("   Verifica la configuración de la API de DeepSeek.")
            
            # Mostrar detalles del error para debugging
            import traceback
            self.stdout.write(f"\n🔍 DETALLES DEL ERROR:")
            self.stdout.write(traceback.format_exc())
        
        self.stdout.write("\n" + "="*60)