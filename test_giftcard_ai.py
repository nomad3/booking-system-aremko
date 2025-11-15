#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de prueba para el servicio de IA de GiftCards

Este script prueba la generación de mensajes personalizados usando DeepSeek AI.

Uso:
    python test_giftcard_ai.py

Requisitos:
    - DEEPSEEK_API_KEY configurado en settings.py o como variable de entorno
    - Dependencia: openai>=1.0.0
"""

import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.services.giftcard_ai_service import GiftCardAIService


def test_generar_mensajes_romantico():
    """Test: Generar 3 mensajes románticos"""
    print("\n" + "="*80)
    print("TEST 1: Generar 3 mensajes románticos")
    print("="*80)

    try:
        mensajes = GiftCardAIService.generar_mensajes(
            tipo_mensaje='romantico',
            nombre='María',
            relacion='esposa',
            detalle='Celebrando nuestro aniversario de bodas, 10 años juntos',
            cantidad=3
        )

        print(f"\n✅ Se generaron {len(mensajes)} mensajes exitosamente:\n")
        for i, mensaje in enumerate(mensajes, 1):
            print(f"{i}. {mensaje}\n")

        return True

    except Exception as e:
        print(f"\n❌ Error: {str(e)}\n")
        return False


def test_generar_mensajes_cumpleanos():
    """Test: Generar 3 mensajes de cumpleaños"""
    print("\n" + "="*80)
    print("TEST 2: Generar 3 mensajes de cumpleaños")
    print("="*80)

    try:
        mensajes = GiftCardAIService.generar_mensajes(
            tipo_mensaje='cumpleanos',
            nombre='Camila',
            relacion='hermana',
            detalle='Cumple 30 años, le encantan las experiencias de relax',
            cantidad=3
        )

        print(f"\n✅ Se generaron {len(mensajes)} mensajes exitosamente:\n")
        for i, mensaje in enumerate(mensajes, 1):
            print(f"{i}. {mensaje}\n")

        return True

    except Exception as e:
        print(f"\n❌ Error: {str(e)}\n")
        return False


def test_regenerar_mensaje():
    """Test: Regenerar un mensaje diferente a los anteriores"""
    print("\n" + "="*80)
    print("TEST 3: Regenerar mensaje único (diferente a previos)")
    print("="*80)

    try:
        # Primero generar mensajes iniciales
        print("\n1. Generando 2 mensajes iniciales...")
        mensajes_previos = GiftCardAIService.generar_mensajes(
            tipo_mensaje='agradecimiento',
            nombre='Andrea',
            relacion='mejor amiga',
            detalle='Siempre me apoya en momentos difíciles',
            cantidad=2
        )

        print("\nMensajes previos generados:")
        for i, mensaje in enumerate(mensajes_previos, 1):
            print(f"{i}. {mensaje}\n")

        # Ahora regenerar uno diferente
        print("\n2. Regenerando un mensaje diferente...")
        nuevo_mensaje = GiftCardAIService.regenerar_mensaje_unico(
            tipo_mensaje='agradecimiento',
            nombre='Andrea',
            relacion='mejor amiga',
            detalle='Siempre me apoya en momentos difíciles',
            mensajes_previos=mensajes_previos
        )

        print(f"\n✅ Nuevo mensaje generado:\n\n{nuevo_mensaje}\n")

        return True

    except Exception as e:
        print(f"\n❌ Error: {str(e)}\n")
        return False


def test_tipo_mensaje_invalido():
    """Test: Intentar generar con tipo de mensaje inválido (debe fallar)"""
    print("\n" + "="*80)
    print("TEST 4: Validación de tipo de mensaje inválido (debe fallar)")
    print("="*80)

    try:
        mensajes = GiftCardAIService.generar_mensajes(
            tipo_mensaje='tipo_invalido',
            nombre='Juan',
            relacion='amigo',
            cantidad=1
        )

        print(f"\n❌ ERROR: Debería haber fallado con tipo_mensaje inválido\n")
        return False

    except ValueError as e:
        print(f"\n✅ Validación correcta - Error esperado: {str(e)}\n")
        return True

    except Exception as e:
        print(f"\n❌ Error inesperado: {str(e)}\n")
        return False


def test_todos_los_tipos():
    """Test: Generar 1 mensaje de cada tipo disponible"""
    print("\n" + "="*80)
    print("TEST 5: Generar 1 mensaje de cada tipo disponible")
    print("="*80)

    tipos = [
        ('romantico', 'Carlos', 'pareja'),
        ('cumpleanos', 'Laura', 'madre'),
        ('aniversario', 'Roberto', 'padre'),
        ('celebracion', 'Sofía', 'prima'),
        ('relajacion', 'Daniela', 'compañera de trabajo'),
        ('parejas', 'Pablo', 'esposo'),
        ('agradecimiento', 'Valentina', 'amiga'),
        ('amistad', 'Martín', 'amigo de la infancia'),
    ]

    resultados = []

    for tipo, nombre, relacion in tipos:
        try:
            print(f"\n→ Generando mensaje tipo '{tipo}' para {nombre} ({relacion})...")
            mensajes = GiftCardAIService.generar_mensajes(
                tipo_mensaje=tipo,
                nombre=nombre,
                relacion=relacion,
                cantidad=1
            )

            print(f"  ✅ Mensaje: {mensajes[0][:80]}...")
            resultados.append(True)

        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            resultados.append(False)

    exitos = sum(resultados)
    total = len(resultados)

    print(f"\n{'='*80}")
    print(f"Resultado: {exitos}/{total} tipos generados exitosamente")
    print(f"{'='*80}\n")

    return exitos == total


def main():
    """Ejecutar todos los tests"""
    print("\n" + "█"*80)
    print("█" + " "*78 + "█")
    print("█" + " "*20 + "TESTS DE GIFTCARD AI SERVICE" + " "*31 + "█")
    print("█" + " "*78 + "█")
    print("█"*80 + "\n")

    tests = [
        ("Mensajes románticos", test_generar_mensajes_romantico),
        ("Mensajes de cumpleaños", test_generar_mensajes_cumpleanos),
        ("Regenerar mensaje único", test_regenerar_mensaje),
        ("Validación tipo inválido", test_tipo_mensaje_invalido),
        ("Todos los tipos de mensaje", test_todos_los_tipos),
    ]

    resultados = []

    for nombre_test, func_test in tests:
        try:
            resultado = func_test()
            resultados.append((nombre_test, resultado))
        except Exception as e:
            print(f"\n❌ Error fatal en {nombre_test}: {str(e)}\n")
            resultados.append((nombre_test, False))

    # Resumen final
    print("\n" + "█"*80)
    print("█" + " "*78 + "█")
    print("█" + " "*28 + "RESUMEN DE TESTS" + " "*34 + "█")
    print("█" + " "*78 + "█")
    print("█"*80 + "\n")

    for nombre, exito in resultados:
        icono = "✅" if exito else "❌"
        estado = "EXITOSO" if exito else "FALLIDO"
        print(f"{icono} {nombre}: {estado}")

    exitos = sum(1 for _, exito in resultados if exito)
    total = len(resultados)

    print("\n" + "="*80)
    print(f"TOTAL: {exitos}/{total} tests exitosos ({int(exitos/total*100)}%)")
    print("="*80 + "\n")

    return exitos == total


if __name__ == '__main__':
    exito = main()
    sys.exit(0 if exito else 1)
