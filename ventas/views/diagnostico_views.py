# -*- coding: utf-8 -*-
"""
Vista de diagnóstico para el sistema de GiftCards
Endpoint: /diagnostico/giftcards/
"""

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db import connection, transaction
from django.db.models import Count, Avg, Max, Min, Q, Sum
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import time
import json

from ..models import GiftCard, GiftCardExperiencia, VentaReserva, Pago


def diagnostico_giftcards(request):
    """
    Endpoint de diagnóstico para identificar problemas de performance
    en el sistema de GiftCards.

    Solo accesible para staff.
    """

    # Verificar que es usuario staff
    if not request.user.is_staff:
        return JsonResponse({'error': 'No autorizado'}, status=403)

    # Iniciar medición de tiempo total
    inicio_total = time.time()

    diagnostico = {
        'timestamp': timezone.now().isoformat(),
        'metricas': {},
        'queries_lentas': [],
        'warnings': [],
        'recomendaciones': []
    }

    # === MÉTRICAS BÁSICAS ===
    try:
        inicio = time.time()

        # Total de GiftCards
        total_giftcards = GiftCard.objects.count()
        tiempo_query = (time.time() - inicio) * 1000

        diagnostico['metricas']['total_giftcards'] = {
            'valor': total_giftcards,
            'tiempo_ms': round(tiempo_query, 2)
        }

        if tiempo_query > 100:
            diagnostico['queries_lentas'].append({
                'query': 'GiftCard.objects.count()',
                'tiempo_ms': round(tiempo_query, 2),
                'problema': 'Query lenta - posible falta de índice'
            })

    except Exception as e:
        diagnostico['warnings'].append(f'Error en total_giftcards: {str(e)}')

    # === GIFTCARDS RECIENTES ===
    try:
        inicio = time.time()
        hace_24h = timezone.now() - timedelta(hours=24)
        giftcards_24h = GiftCard.objects.filter(fecha_emision__gte=hace_24h).count()
        tiempo_query = (time.time() - inicio) * 1000

        diagnostico['metricas']['giftcards_ultimas_24h'] = {
            'valor': giftcards_24h,
            'tiempo_ms': round(tiempo_query, 2)
        }

        if tiempo_query > 200:
            diagnostico['queries_lentas'].append({
                'query': 'GiftCard.objects.filter(fecha_emision__gte=hace_24h).count()',
                'tiempo_ms': round(tiempo_query, 2),
                'problema': 'Filtro por fecha lento - verificar índice en fecha_emision'
            })
            diagnostico['recomendaciones'].append(
                'Agregar índice en GiftCard.fecha_emision: db_index=True'
            )

    except Exception as e:
        diagnostico['warnings'].append(f'Error en giftcards_24h: {str(e)}')

    # === ESTADO DE GIFTCARDS ===
    try:
        inicio = time.time()
        estado_counts = GiftCard.objects.values('estado').annotate(total=Count('id'))
        tiempo_query = (time.time() - inicio) * 1000

        diagnostico['metricas']['giftcards_por_estado'] = {
            'valores': {item['estado']: item['total'] for item in estado_counts},
            'tiempo_ms': round(tiempo_query, 2)
        }

    except Exception as e:
        diagnostico['warnings'].append(f'Error en estado_counts: {str(e)}')

    # === EXPERIENCIAS ACTIVAS ===
    try:
        inicio = time.time()
        experiencias_activas = GiftCardExperiencia.objects.filter(activo=True).count()
        tiempo_query = (time.time() - inicio) * 1000

        diagnostico['metricas']['experiencias_activas'] = {
            'valor': experiencias_activas,
            'tiempo_ms': round(tiempo_query, 2)
        }

    except Exception as e:
        diagnostico['warnings'].append(f'Error en experiencias_activas: {str(e)}')

    # === VENTAS CON GIFTCARDS ===
    try:
        inicio = time.time()
        ventas_con_giftcards = VentaReserva.objects.filter(
            giftcards__isnull=False
        ).distinct().count()
        tiempo_query = (time.time() - inicio) * 1000

        diagnostico['metricas']['ventas_con_giftcards'] = {
            'valor': ventas_con_giftcards,
            'tiempo_ms': round(tiempo_query, 2)
        }

        if tiempo_query > 500:
            diagnostico['queries_lentas'].append({
                'query': 'VentaReserva con giftcards (JOIN)',
                'tiempo_ms': round(tiempo_query, 2),
                'problema': 'JOIN lento - verificar relación e índices'
            })

    except Exception as e:
        diagnostico['warnings'].append(f'Error en ventas_con_giftcards: {str(e)}')

    # === PAGOS CON GIFTCARD ===
    try:
        inicio = time.time()
        pagos_giftcard = Pago.objects.filter(metodo_pago='giftcard').count()
        tiempo_query = (time.time() - inicio) * 1000

        diagnostico['metricas']['pagos_con_giftcard'] = {
            'valor': pagos_giftcard,
            'tiempo_ms': round(tiempo_query, 2)
        }

        if tiempo_query > 300:
            diagnostico['queries_lentas'].append({
                'query': 'Pago.objects.filter(metodo_pago=giftcard).count()',
                'tiempo_ms': round(tiempo_query, 2),
                'problema': 'Query lenta - agregar índice en metodo_pago'
            })
            diagnostico['recomendaciones'].append(
                'Agregar índice en Pago.metodo_pago: db_index=True'
            )

    except Exception as e:
        diagnostico['warnings'].append(f'Error en pagos_giftcard: {str(e)}')

    # === GIFTCARDS CON SALDO ===
    try:
        inicio = time.time()
        giftcards_con_saldo = GiftCard.objects.filter(
            monto_disponible__gt=0,
            fecha_vencimiento__gte=timezone.now().date()
        ).count()
        tiempo_query = (time.time() - inicio) * 1000

        diagnostico['metricas']['giftcards_con_saldo_activas'] = {
            'valor': giftcards_con_saldo,
            'tiempo_ms': round(tiempo_query, 2)
        }

        if tiempo_query > 400:
            diagnostico['queries_lentas'].append({
                'query': 'GiftCards con saldo y no vencidas',
                'tiempo_ms': round(tiempo_query, 2),
                'problema': 'Filtros múltiples lentos - verificar índices compuestos'
            })
            diagnostico['recomendaciones'].append(
                'Considerar índice compuesto en (monto_disponible, fecha_vencimiento)'
            )

    except Exception as e:
        diagnostico['warnings'].append(f'Error en giftcards_con_saldo: {str(e)}')

    # === QUERIES N+1 POTENCIALES ===
    diagnostico['queries_n_plus_1'] = [
        {
            'ubicacion': 'giftcard_menu view',
            'problema': 'GiftCardExperiencia.objects.filter() sin select_related',
            'solucion': 'Agregar .select_related() si hay FK'
        },
        {
            'ubicacion': 'crear_giftcard view',
            'problema': 'Posible creación de Cliente + VentaReserva + GiftCard en serie',
            'solucion': 'Usar bulk_create o transacciones optimizadas'
        }
    ]

    # === ÍNDICES RECOMENDADOS ===
    diagnostico['indices_recomendados'] = [
        {
            'modelo': 'GiftCard',
            'campo': 'fecha_emision',
            'razon': 'Filtros frecuentes por rango de fechas'
        },
        {
            'modelo': 'GiftCard',
            'campo': 'estado',
            'razon': 'Filtros frecuentes por estado'
        },
        {
            'modelo': 'GiftCard',
            'campo': 'codigo',
            'razon': 'Búsquedas por código (ya tiene unique=True)'
        },
        {
            'modelo': 'Pago',
            'campo': 'metodo_pago',
            'razon': 'Filtros frecuentes por método de pago'
        },
        {
            'modelo': 'GiftCardExperiencia',
            'campo': 'activo',
            'razon': 'Filtros frecuentes por experiencias activas'
        }
    ]

    # === CONFIGURACIÓN DE GUNICORN ===
    diagnostico['configuracion_servidor'] = {
        'timeout_recomendado': '60 segundos (aumentar de 30)',
        'workers_recomendado': '2-4 workers',
        'worker_class': 'sync (actual) - considerar gevent para I/O'
    }

    # === POSIBLES BOTTLENECKS ===
    diagnostico['bottlenecks_potenciales'] = [
        {
            'area': 'Generación de mensajes IA',
            'descripcion': 'API externa de DeepSeek puede tardar 3-10 segundos',
            'solucion': 'Mover a tarea asíncrona (Celery) o usar cache'
        },
        {
            'area': 'Generación de PDF',
            'descripcion': 'Renderizado de PDF puede tardar 2-5 segundos',
            'solucion': 'Generar PDF asíncronamente y notificar al usuario'
        },
        {
            'area': 'Envío de emails',
            'descripcion': 'SMTP puede tardar 1-3 segundos por email',
            'solucion': 'Usar cola de emails (Celery + Redis)'
        },
        {
            'area': 'Queries sin optimizar',
            'descripcion': 'Falta de select_related/prefetch_related',
            'solucion': 'Optimizar queries en views críticas'
        }
    ]

    # Tiempo total del diagnóstico
    tiempo_total = (time.time() - inicio_total) * 1000
    diagnostico['tiempo_diagnostico_ms'] = round(tiempo_total, 2)

    # === ANÁLISIS AUTOMÁTICO ===
    diagnostico['analisis_automatico'] = []

    if len(diagnostico['queries_lentas']) > 0:
        diagnostico['analisis_automatico'].append({
            'severidad': 'ALTA',
            'mensaje': f'Se detectaron {len(diagnostico["queries_lentas"])} queries lentas (>100ms)'
        })

    if tiempo_total > 2000:
        diagnostico['analisis_automatico'].append({
            'severidad': 'MEDIA',
            'mensaje': f'El diagnóstico tardó {round(tiempo_total/1000, 2)}s - la BD puede estar bajo carga'
        })

    # Retornar como JSON o HTML según el parámetro
    formato = request.GET.get('formato', 'html')

    if formato == 'json':
        return JsonResponse(diagnostico, json_dumps_params={'indent': 2})
    else:
        # Renderizar template HTML bonito
        return render(request, 'ventas/diagnostico_giftcards.html', {
            'diagnostico': diagnostico,
            'diagnostico_json': json.dumps(diagnostico, indent=2)
        })


@staff_member_required
def revisar_inconsistencias_giftcards(request):
    """
    Vista para revisar inconsistencias en saldos de GiftCards.
    Analiza todas las GiftCards que han sido usadas y compara el saldo
    actual con el saldo esperado basado en los pagos registrados.
    """
    # Obtener todas las GiftCards que han sido usadas en pagos
    giftcards_usadas = GiftCard.objects.filter(
        pago__isnull=False
    ).distinct().select_related(
        'cliente_comprador',
        'cliente_destinatario',
        'venta_reserva'
    )

    inconsistencias = []
    total_analizado = giftcards_usadas.count()

    for gc in giftcards_usadas:
        # Calcular total usado en pagos
        total_usado = Pago.objects.filter(
            giftcard=gc,
            metodo_pago='giftcard'
        ).aggregate(total=Sum('monto'))['total'] or Decimal('0')

        # Calcular saldo esperado
        saldo_esperado = gc.monto_inicial - total_usado
        diferencia = gc.monto_disponible - saldo_esperado

        # Si hay inconsistencia, agregarla a la lista
        if diferencia != 0:
            # Obtener los pagos para mostrar detalles
            pagos = Pago.objects.filter(
                giftcard=gc,
                metodo_pago='giftcard'
            ).select_related('venta_reserva').order_by('fecha_pago')

            inconsistencias.append({
                'giftcard': gc,
                'total_usado': total_usado,
                'saldo_actual': gc.monto_disponible,
                'saldo_esperado': saldo_esperado,
                'diferencia': diferencia,
                'pagos': pagos,
                'estado_actual': gc.estado,
                'estado_esperado': 'cobrado' if saldo_esperado == 0 else 'por_cobrar'
            })

    context = {
        'total_analizado': total_analizado,
        'total_inconsistencias': len(inconsistencias),
        'inconsistencias': inconsistencias,
    }

    return render(request, 'ventas/revisar_inconsistencias_giftcards.html', context)


@staff_member_required
def corregir_inconsistencias_giftcards(request):
    """
    Vista para corregir automáticamente las inconsistencias en saldos de GiftCards.
    Solo acepta método POST por seguridad.
    """
    if request.method != 'POST':
        messages.error(request, 'Método no permitido. Usa el botón de corrección.')
        return redirect('admin:ventas_giftcard_changelist')

    # Obtener todas las GiftCards con inconsistencias
    giftcards_usadas = GiftCard.objects.filter(
        pago__isnull=False
    ).distinct()

    correcciones_aplicadas = 0
    errores = 0

    for gc in giftcards_usadas:
        try:
            # Calcular total usado en pagos
            total_usado = Pago.objects.filter(
                giftcard=gc,
                metodo_pago='giftcard'
            ).aggregate(total=Sum('monto'))['total'] or Decimal('0')

            # Calcular saldo esperado
            saldo_esperado = gc.monto_inicial - total_usado

            # Verificar si hay inconsistencia
            if gc.monto_disponible != saldo_esperado:
                # Determinar nuevo estado
                nuevo_estado = 'cobrado' if saldo_esperado == 0 else 'por_cobrar'

                # Aplicar corrección
                with transaction.atomic():
                    gc.monto_disponible = saldo_esperado
                    gc.estado = nuevo_estado
                    gc.save()

                correcciones_aplicadas += 1

        except Exception as e:
            errores += 1
            continue

    # Mostrar mensaje de éxito
    if correcciones_aplicadas > 0:
        messages.success(
            request,
            f'✓ Se corrigieron {correcciones_aplicadas} GiftCard(s) exitosamente.'
        )
    else:
        messages.info(
            request,
            '✓ No se encontraron inconsistencias. Todas las GiftCards están correctas.'
        )

    if errores > 0:
        messages.warning(
            request,
            f'⚠ Se encontraron {errores} errores durante la corrección.'
        )

    return redirect('admin:ventas_giftcard_changelist')
