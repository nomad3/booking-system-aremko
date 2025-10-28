"""
EmailPremioService - Servicio para envío de emails de premios con rate limiting
Maneja el envío de premios con control anti-spam y múltiples líneas de asunto
"""
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from ventas.models import ClientePremio
from ventas.services.premio_service import PremioService
from datetime import timedelta
import random
import logging
import time

logger = logging.getLogger(__name__)


class EmailPremioService:
    """Servicio para envío de emails de premios con rate limiting"""

    # Delay mínimo entre envíos (30 minutos)
    MIN_DELAY_SECONDS = 30 * 60  # 1800 segundos

    # Líneas de asunto por tipo de premio (anti-spam)
    SUBJECT_LINES = {
        'descuento_bienvenida': [
            '¡Bienvenido/a a Aremko! 🎁 Tenemos un regalo para ti',
            '🎉 ¡Gracias por elegirnos! Tu premio de bienvenida',
            'Un regalo especial te espera en Aremko ✨',
            '¡Bienvenido/a! Disfruta de tu descuento exclusivo',
            '🌟 Tu premio de bienvenida está listo',
        ],
        'tinas_gratis': [
            '🏆 ¡Felicitaciones! Has alcanzado un nuevo nivel',
            '¡Nuevo hito desbloqueado! 🎯 Tu premio te espera',
            '🌟 ¡Lo lograste! Premio exclusivo para ti',
            '¡Celebremos juntos! 🎉 Has ganado un premio especial',
            '🎁 Un reconocimiento a tu fidelidad',
        ],
        'noche_gratis': [
            '👑 ¡Bienvenido/a al club VIP de Aremko!',
            '🏆 Premio VIP Exclusivo - ¡Lo lograste!',
            '⭐ Felicitaciones Cliente VIP - Tu premio especial',
            '🌟 Has alcanzado el nivel VIP - Premio exclusivo',
            '👑 ¡Eres VIP! Tu noche de alojamiento te espera',
        ]
    }

    # Templates por tipo de premio
    TEMPLATES = {
        'descuento_bienvenida': 'emails/premio_bienvenida_email.html',
        'tinas_gratis': 'emails/premio_tinas_gratis_email.html',
        'noche_gratis': 'emails/premio_noche_gratis_email.html',
    }

    # Almacenamiento en memoria del último envío (en producción usar cache/redis)
    _last_send_time = None

    @classmethod
    def _get_random_subject(cls, tipo_premio: str) -> str:
        """
        Obtiene una línea de asunto aleatoria para el tipo de premio

        Args:
            tipo_premio: Tipo del premio

        Returns:
            Línea de asunto aleatoria
        """
        subjects = cls.SUBJECT_LINES.get(tipo_premio, ['Premio Aremko'])
        return random.choice(subjects)

    @classmethod
    def _get_template_path(cls, tipo_premio: str) -> str:
        """
        Obtiene el path del template para el tipo de premio

        Args:
            tipo_premio: Tipo del premio

        Returns:
            Path del template
        """
        return cls.TEMPLATES.get(tipo_premio, 'emails/premio_bienvenida_email.html')

    @classmethod
    def _wait_if_needed(cls) -> float:
        """
        Espera el tiempo necesario para respetar el rate limit

        Returns:
            Segundos esperados
        """
        if cls._last_send_time is None:
            return 0

        elapsed = (timezone.now() - cls._last_send_time).total_seconds()

        if elapsed < cls.MIN_DELAY_SECONDS:
            wait_time = cls.MIN_DELAY_SECONDS - elapsed
            logger.info(f"Rate limiting: Esperando {wait_time:.0f} segundos antes del próximo envío...")
            time.sleep(wait_time)
            return wait_time

        return 0

    @classmethod
    def enviar_premio(cls, cliente_premio_id: int, force: bool = False) -> dict:
        """
        Envía el email de un premio específico

        Args:
            cliente_premio_id: ID del ClientePremio
            force: Ignorar rate limiting (usar con precaución)

        Returns:
            Dict con resultado:
            {
                'success': bool,
                'message': str,
                'email_sent': bool,
                'wait_time': float (segundos esperados)
            }
        """
        try:
            # Obtener el premio
            cliente_premio = ClientePremio.objects.select_related(
                'cliente', 'premio'
            ).get(id=cliente_premio_id)

            # Validar estado
            if cliente_premio.estado != 'aprobado':
                return {
                    'success': False,
                    'message': f'Premio no está aprobado (estado: {cliente_premio.estado})',
                    'email_sent': False,
                    'wait_time': 0
                }

            # Validar vigencia
            if not cliente_premio.esta_vigente():
                return {
                    'success': False,
                    'message': 'Premio expirado',
                    'email_sent': False,
                    'wait_time': 0
                }

            # Rate limiting (salvo force=True)
            wait_time = 0
            if not force:
                wait_time = cls._wait_if_needed()

            # Preparar datos para el template
            context = {
                'cliente': cliente_premio.cliente,
                'cliente_premio': cliente_premio,
                'premio': cliente_premio.premio,
            }

            # Obtener template y asunto
            template_path = cls._get_template_path(cliente_premio.premio.tipo)
            asunto = cls._get_random_subject(cliente_premio.premio.tipo)

            # Renderizar HTML
            html_content = render_to_string(template_path, context)

            # Enviar email
            send_mail(
                subject=asunto,
                message='',  # Texto plano vacío
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[cliente_premio.cliente.email],
                html_message=html_content,
                fail_silently=False,
            )

            # Actualizar registro usando PremioService
            PremioService.marcar_premio_enviado(
                premio_id=cliente_premio_id,
                asunto=asunto,
                cuerpo=html_content[:500]  # Guardar primeros 500 caracteres
            )

            # Actualizar último envío
            cls._last_send_time = timezone.now()

            logger.info(
                f"Premio enviado: ID {cliente_premio_id}, "
                f"Cliente: {cliente_premio.cliente.email}, "
                f"Tipo: {cliente_premio.premio.tipo}"
            )

            return {
                'success': True,
                'message': f'Email enviado exitosamente a {cliente_premio.cliente.email}',
                'email_sent': True,
                'wait_time': wait_time
            }

        except ClientePremio.DoesNotExist:
            return {
                'success': False,
                'message': f'Premio {cliente_premio_id} no existe',
                'email_sent': False,
                'wait_time': 0
            }
        except Exception as e:
            logger.error(f"Error enviando premio {cliente_premio_id}: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'Error enviando email: {str(e)}',
                'email_sent': False,
                'wait_time': 0
            }

    @classmethod
    def enviar_premios_pendientes(cls, limit: int = 10, force: bool = False) -> dict:
        """
        Envía emails de premios aprobados pendientes de envío

        Args:
            limit: Número máximo de premios a enviar
            force: Ignorar rate limiting (usar con precaución)

        Returns:
            Dict con estadísticas:
            {
                'total_procesados': int,
                'enviados': int,
                'errores': int,
                'detalles': list,
                'tiempo_total': float (segundos)
            }
        """
        inicio = time.time()

        # Obtener premios aprobados listos para enviar
        premios = PremioService.obtener_premios_aprobados(limit=limit)

        resultado = {
            'total_procesados': 0,
            'enviados': 0,
            'errores': 0,
            'detalles': [],
            'tiempo_total': 0
        }

        for premio in premios:
            resultado['total_procesados'] += 1

            # Intentar enviar
            res = cls.enviar_premio(premio.id, force=force)

            if res['success']:
                resultado['enviados'] += 1
            else:
                resultado['errores'] += 1

            resultado['detalles'].append({
                'premio_id': premio.id,
                'cliente': premio.cliente.nombre,
                'email': premio.cliente.email,
                'success': res['success'],
                'message': res['message'],
                'wait_time': res['wait_time']
            })

        resultado['tiempo_total'] = time.time() - inicio

        logger.info(
            f"Envío batch completado: {resultado['enviados']} enviados, "
            f"{resultado['errores']} errores, "
            f"{resultado['tiempo_total']:.1f}s"
        )

        return resultado

    @classmethod
    def preview_email(cls, cliente_premio_id: int) -> str:
        """
        Genera preview HTML del email sin enviarlo

        Args:
            cliente_premio_id: ID del ClientePremio

        Returns:
            HTML renderizado del email
        """
        try:
            cliente_premio = ClientePremio.objects.select_related(
                'cliente', 'premio'
            ).get(id=cliente_premio_id)

            context = {
                'cliente': cliente_premio.cliente,
                'cliente_premio': cliente_premio,
                'premio': cliente_premio.premio,
            }

            template_path = cls._get_template_path(cliente_premio.premio.tipo)
            return render_to_string(template_path, context)

        except ClientePremio.DoesNotExist:
            return f"<h1>Error: Premio {cliente_premio_id} no existe</h1>"
        except Exception as e:
            return f"<h1>Error generando preview: {str(e)}</h1>"

    @classmethod
    def test_email(cls, email: str, tipo_premio: str = 'descuento_bienvenida') -> bool:
        """
        Envía un email de prueba

        Args:
            email: Email destino
            tipo_premio: Tipo de premio a probar

        Returns:
            True si se envió exitosamente
        """
        try:
            # Crear contexto de prueba
            from ventas.models import Cliente, Premio
            from decimal import Decimal

            context = {
                'cliente': type('obj', (object,), {
                    'nombre': 'Cliente de Prueba',
                    'email': email
                }),
                'cliente_premio': type('obj', (object,), {
                    'codigo_unico': 'TEST12345678',
                    'fecha_expiracion': timezone.now() + timedelta(days=30),
                    'tramo_al_ganar': 5,
                    'gasto_total_al_ganar': Decimal('250000'),
                }),
                'premio': type('obj', (object,), {
                    'nombre': 'Premio de Prueba',
                    'descripcion_corta': 'Este es un email de prueba del sistema de premios.',
                    'descripcion_legal': 'Este es solo un email de prueba. No es un premio real.',
                    'tipo': tipo_premio
                })
            }

            template_path = cls._get_template_path(tipo_premio)
            asunto = f'[TEST] {cls._get_random_subject(tipo_premio)}'
            html_content = render_to_string(template_path, context)

            send_mail(
                subject=asunto,
                message='Email de prueba',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_content,
                fail_silently=False,
            )

            logger.info(f"Email de prueba enviado a {email}")
            return True

        except Exception as e:
            logger.error(f"Error enviando email de prueba: {e}", exc_info=True)
            return False

    @classmethod
    def obtener_estadisticas_envio(cls) -> dict:
        """
        Obtiene estadísticas del sistema de envío

        Returns:
            Dict con estadísticas de envíos
        """
        from django.db.models import Count

        stats = ClientePremio.objects.filter(
            estado='enviado'
        ).values('premio__tipo').annotate(total=Count('id'))

        return {
            'total_enviados': sum(item['total'] for item in stats),
            'por_tipo': {item['premio__tipo']: item['total'] for item in stats},
            'ultimo_envio': cls._last_send_time,
            'puede_enviar_ahora': (
                cls._last_send_time is None or
                (timezone.now() - cls._last_send_time).total_seconds() >= cls.MIN_DELAY_SECONDS
            )
        }
