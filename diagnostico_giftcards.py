"""
Script de diagnóstico para identificar problemas con GiftCards
Ejecutar: python3 manage.py shell < diagnostico_giftcards.py
"""

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import GiftCardExperiencia

print("=" * 80)
print("DIAGNÓSTICO DE GIFTCARDS - CONFIGURACIÓN")
print("=" * 80)

# Obtener todas las experiencias
todas = GiftCardExperiencia.objects.all()
activas = GiftCardExperiencia.objects.filter(activo=True)
inactivas = GiftCardExperiencia.objects.filter(activo=False)

print(f"\n📊 RESUMEN GENERAL")
print(f"   Total de experiencias: {todas.count()}")
print(f"   ✅ Activas: {activas.count()}")
print(f"   ❌ Inactivas: {inactivas.count()}")

# Análisis de experiencias activas
print(f"\n{'=' * 80}")
print(f"✅ EXPERIENCIAS ACTIVAS (visibles en el wizard)")
print(f"{'=' * 80}")

if activas.count() == 0:
    print("\n⚠️  NO HAY EXPERIENCIAS ACTIVAS")
    print("   Esto explica por qué no se pueden agregar giftcards al carrito.")
    print("   Solución: Activar experiencias en el admin de Django.")
else:
    for exp in activas.order_by('categoria', 'orden'):
        print(f"\n{exp.id}. {exp.nombre}")
        print(f"   ID Experiencia: {exp.id_experiencia}")
        print(f"   Categoría: {exp.get_categoria_display()}")
        print(f"   Orden: {exp.orden}")

        # Verificar precio
        if exp.monto_fijo:
            print(f"   💰 Precio fijo: ${exp.monto_fijo:,}")
        elif exp.montos_sugeridos:
            print(f"   💰 Montos sugeridos: {exp.montos_sugeridos}")
        else:
            print(f"   ⚠️  SIN PRECIO CONFIGURADO (esto puede causar problemas)")

        # Verificar imagen
        if exp.imagen:
            print(f"   🖼️  Imagen: {exp.imagen.url}")
            # Verificar si el archivo existe
            if exp.imagen.storage.exists(exp.imagen.name):
                print(f"      ✅ Archivo existe")
            else:
                print(f"      ❌ ARCHIVO NO EXISTE (ruta rota)")
        else:
            print(f"   ⚠️  Sin imagen (se mostrará ícono por defecto)")

        # Verificar descripciones
        if not exp.descripcion:
            print(f"   ⚠️  Sin descripción corta")
        if not exp.descripcion_giftcard:
            print(f"   ⚠️  Sin descripción para giftcard")

# Análisis de experiencias inactivas
if inactivas.count() > 0:
    print(f"\n{'=' * 80}")
    print(f"❌ EXPERIENCIAS INACTIVAS (NO visibles en el wizard)")
    print(f"{'=' * 80}")

    for exp in inactivas.order_by('categoria', 'nombre'):
        print(f"\n{exp.id}. {exp.nombre}")
        print(f"   ID Experiencia: {exp.id_experiencia}")
        print(f"   Categoría: {exp.get_categoria_display()}")
        if exp.monto_fijo:
            print(f"   Precio: ${exp.monto_fijo:,}")
        print(f"   💡 Para activar: Editar en admin y marcar como 'Activo'")

# Problemas comunes
print(f"\n{'=' * 80}")
print(f"🔍 PROBLEMAS DETECTADOS")
print(f"{'=' * 80}")

problemas = []

# 1. No hay experiencias activas
if activas.count() == 0:
    problemas.append({
        'tipo': 'CRÍTICO',
        'mensaje': 'No hay experiencias activas',
        'impacto': 'Los usuarios no pueden agregar giftcards al carrito',
        'solucion': 'Activar al menos una experiencia en /admin/ventas/giftcardexperiencia/'
    })

# 2. Experiencias sin precio
sin_precio = activas.filter(monto_fijo__isnull=True, montos_sugeridos__exact=[])
if sin_precio.exists():
    problemas.append({
        'tipo': 'ALTO',
        'mensaje': f'{sin_precio.count()} experiencias activas sin precio configurado',
        'impacto': 'El usuario no sabrá cuánto pagar',
        'solucion': 'Configurar monto_fijo o montos_sugeridos para cada experiencia'
    })
    for exp in sin_precio:
        print(f"   - {exp.nombre} (ID: {exp.id_experiencia})")

# 3. Experiencias sin imagen
sin_imagen = activas.filter(imagen='')
if sin_imagen.exists():
    problemas.append({
        'tipo': 'MEDIO',
        'mensaje': f'{sin_imagen.count()} experiencias activas sin imagen',
        'impacto': 'Se mostrará un ícono genérico en lugar de foto',
        'solucion': 'Subir imágenes (800x600px recomendado) en el admin'
    })
    for exp in sin_imagen:
        print(f"   - {exp.nombre} (ID: {exp.id_experiencia})")

# 4. Imágenes rotas
imagenes_rotas = []
for exp in activas:
    if exp.imagen and not exp.imagen.storage.exists(exp.imagen.name):
        imagenes_rotas.append(exp)

if imagenes_rotas:
    problemas.append({
        'tipo': 'ALTO',
        'mensaje': f'{len(imagenes_rotas)} experiencias con imágenes rotas',
        'impacto': 'Error 404 al cargar las imágenes',
        'solucion': 'Volver a subir las imágenes o corregir las rutas'
    })
    for exp in imagenes_rotas:
        print(f"   - {exp.nombre}: {exp.imagen.name}")

# 5. Descripciones faltantes
sin_descripcion = activas.filter(descripcion='') | activas.filter(descripcion_giftcard='')
if sin_descripcion.exists():
    problemas.append({
        'tipo': 'BAJO',
        'mensaje': f'{sin_descripcion.count()} experiencias sin descripciones completas',
        'impacto': 'Información incompleta para el usuario',
        'solucion': 'Completar descripcion y descripcion_giftcard'
    })

# Mostrar resumen de problemas
if not problemas:
    print("\n✅ No se detectaron problemas de configuración")
else:
    for i, problema in enumerate(problemas, 1):
        print(f"\n{i}. [{problema['tipo']}] {problema['mensaje']}")
        print(f"   Impacto: {problema['impacto']}")
        print(f"   Solución: {problema['solucion']}")

# Recomendaciones
print(f"\n{'=' * 80}")
print(f"💡 RECOMENDACIONES")
print(f"{'=' * 80}")
print("""
1. Verificar el admin de Django:
   URL: /admin/ventas/giftcardexperiencia/

2. Para activar una experiencia:
   - Entrar al admin
   - Seleccionar la experiencia
   - Marcar el checkbox "Activo"
   - Guardar cambios

3. Para crear una nueva experiencia:
   - Ir a /admin/ventas/giftcardexperiencia/add/
   - Completar todos los campos requeridos:
     * id_experiencia (único, ej: 'tinas_calientes')
     * categoria (tinas, masajes, faciales, packs, valor)
     * nombre (nombre visible para el usuario)
     * descripcion (descripción corta para el menú)
     * descripcion_giftcard (descripción detallada para la giftcard)
     * imagen (subir foto 800x600px)
     * monto_fijo O montos_sugeridos (al menos uno)
     * activo = True
     * orden (número para ordenar la lista)

4. Estructura recomendada de precios:
   - Experiencias específicas (tinas, masajes): monto_fijo
   - Tarjetas de valor libre: montos_sugeridos = [30000, 50000, 75000, 100000]

5. Testing:
   - Después de configurar, visitar /giftcards/
   - Verificar que se muestren todas las experiencias activas
   - Intentar completar el wizard hasta agregar al carrito
""")

print(f"\n{'=' * 80}")
print("FIN DEL DIAGNÓSTICO")
print(f"{'=' * 80}\n")
