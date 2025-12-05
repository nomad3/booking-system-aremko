#!/usr/bin/env python
"""
Script para limpiar emails duplicados 'cliente@aremko.cl'
Este script busca todos los clientes con el email 'cliente@aremko.cl'
y lo elimina (establece a null/vacío)

Autor: Sistema de Booking Aremko
Fecha: 2025-12-05
"""

import os
import sys
import django

# Configurar el entorno de Django
sys.path.insert(0, '/app')  # Ajustar según la estructura de Render
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import transaction
from ventas.models import Cliente
from datetime import datetime


def limpiar_emails_duplicados():
    """
    Función principal para limpiar emails duplicados
    """
    print("="*60)
    print("SCRIPT DE LIMPIEZA DE EMAILS DUPLICADOS")
    print("="*60)
    print(f"Fecha de ejecución: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-"*60)

    # Email a buscar
    email_duplicado = "cliente@aremko.cl"

    try:
        # Buscar clientes con el email duplicado
        print(f"\n1. Buscando clientes con email: '{email_duplicado}'...")
        clientes_afectados = Cliente.objects.filter(email=email_duplicado)
        cantidad = clientes_afectados.count()

        if cantidad == 0:
            print(f"   ✓ No se encontraron clientes con el email '{email_duplicado}'")
            print("   No hay nada que actualizar.")
            return

        print(f"   ✓ Se encontraron {cantidad} clientes con este email")

        # Mostrar primeros 10 clientes afectados como muestra
        print("\n2. Muestra de clientes afectados (primeros 10):")
        print("-"*60)
        for cliente in clientes_afectados[:10]:
            print(f"   ID: {cliente.id:6} | Nombre: {cliente.nombre[:30].ljust(30)} | Tel: {cliente.telefono}")
        if cantidad > 10:
            print(f"   ... y {cantidad - 10} clientes más")

        # Confirmar antes de proceder
        print("\n3. Confirmación de seguridad:")
        print("-"*60)
        print(f"   ⚠️  Se van a actualizar {cantidad} clientes")
        print(f"   ⚠️  El email '{email_duplicado}' será eliminado (establecido a null)")
        print("\n   ¿Desea continuar? (escriba 'SI' para confirmar): ", end="")

        # En Render, normalmente no hay entrada interactiva, así que comentamos esto
        # Para producción, eliminar la confirmación interactiva
        # confirmacion = input().strip()
        # if confirmacion != 'SI':
        #     print("\n   ✗ Operación cancelada por el usuario")
        #     return

        # Para ejecución automática en Render, continuar directamente
        print("\n   [Modo automático - continuando con la actualización]")

        # Realizar la actualización dentro de una transacción
        print("\n4. Ejecutando actualización...")
        print("-"*60)

        with transaction.atomic():
            # Actualizar todos los registros de una vez
            actualizados = clientes_afectados.update(email=None)
            print(f"   ✓ Se actualizaron {actualizados} registros exitosamente")
            print(f"   ✓ Los emails han sido establecidos a null/vacío")

        # Verificar el resultado
        print("\n5. Verificación post-actualización:")
        print("-"*60)
        clientes_restantes = Cliente.objects.filter(email=email_duplicado).count()
        if clientes_restantes == 0:
            print(f"   ✓ Verificación exitosa: No quedan clientes con el email '{email_duplicado}'")
        else:
            print(f"   ⚠️  ADVERTENCIA: Aún quedan {clientes_restantes} clientes con el email duplicado")

        # Estadísticas finales
        print("\n6. Resumen de la operación:")
        print("-"*60)
        print(f"   • Clientes procesados: {actualizados}")
        print(f"   • Email eliminado: '{email_duplicado}'")
        print(f"   • Estado: COMPLETADO")

    except Exception as e:
        print(f"\n   ✗ ERROR: {str(e)}")
        print("   La operación ha sido revertida")
        raise

    print("\n" + "="*60)
    print("SCRIPT FINALIZADO EXITOSAMENTE")
    print("="*60)


if __name__ == "__main__":
    limpiar_emails_duplicados()