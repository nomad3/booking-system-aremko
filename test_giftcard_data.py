"""
Script de prueba para verificar el método to_dict() de GiftCardExperiencia
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import GiftCardExperiencia
import json

print("=" * 80)
print("PRUEBA DE SERIALIZACIÓN DE GIFTCARDS")
print("=" * 80)

# Obtener todas las experiencias activas (igual que en la vista)
experiencias_db = GiftCardExperiencia.objects.filter(activo=True).order_by('categoria', 'orden', 'nombre')

print(f"\n✅ Total experiencias activas: {experiencias_db.count()}")

# Convertir a diccionarios (igual que en giftcard_wizard view)
try:
    experiencias = [exp.to_dict() for exp in experiencias_db]
    print(f"✅ Conversión a dict exitosa: {len(experiencias)} experiencias")
except Exception as e:
    print(f"❌ ERROR al convertir a dict: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Intentar serializar a JSON (lo que hace Django en el template)
try:
    experiencias_json = json.dumps(experiencias, ensure_ascii=False, indent=2)
    print(f"✅ Serialización a JSON exitosa")
    print(f"\n📄 JSON generado (primeros 500 caracteres):")
    print(experiencias_json[:500])
    print("...")
except Exception as e:
    print(f"❌ ERROR al serializar a JSON: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Verificar estructura de cada experiencia
print(f"\n{'=' * 80}")
print("DETALLE DE CADA EXPERIENCIA")
print(f"{'=' * 80}")

for i, exp_dict in enumerate(experiencias, 1):
    print(f"\n{i}. {exp_dict.get('nombre', 'SIN NOMBRE')}")
    print(f"   ID: {exp_dict.get('id', 'SIN ID')}")
    print(f"   Categoría: {exp_dict.get('categoria', 'SIN CATEGORIA')}")
    print(f"   Descripción: {exp_dict.get('descripcion', 'SIN DESCRIPCION')[:50]}...")

    # Verificar precio
    if exp_dict.get('monto_fijo'):
        print(f"   💰 Monto fijo: ${exp_dict['monto_fijo']:,}")
    elif exp_dict.get('montos_sugeridos'):
        print(f"   💰 Montos sugeridos: {exp_dict['montos_sugeridos']}")
    else:
        print(f"   ⚠️  SIN PRECIO")

    # Verificar imagen
    imagen_url = exp_dict.get('imagen', '')
    if imagen_url:
        print(f"   🖼️  Imagen: {imagen_url}")
    else:
        print(f"   ⚠️  SIN IMAGEN")

    # Verificar campos críticos para el JavaScript
    campos_faltantes = []
    if not exp_dict.get('id'):
        campos_faltantes.append('id')
    if not exp_dict.get('nombre'):
        campos_faltantes.append('nombre')
    if not exp_dict.get('descripcion_giftcard'):
        campos_faltantes.append('descripcion_giftcard')

    if campos_faltantes:
        print(f"   ❌ CAMPOS FALTANTES: {', '.join(campos_faltantes)}")

# Verificar problemas comunes
print(f"\n{'=' * 80}")
print("PROBLEMAS DETECTADOS")
print(f"{'=' * 80}")

problemas_encontrados = []

# 1. Experiencias sin ID
sin_id = [exp for exp in experiencias if not exp.get('id')]
if sin_id:
    problemas_encontrados.append(f"❌ {len(sin_id)} experiencias sin ID")

# 2. Experiencias sin nombre
sin_nombre = [exp for exp in experiencias if not exp.get('nombre')]
if sin_nombre:
    problemas_encontrados.append(f"❌ {len(sin_nombre)} experiencias sin nombre")

# 3. Experiencias sin descripción para giftcard
sin_desc_gc = [exp for exp in experiencias if not exp.get('descripcion_giftcard')]
if sin_desc_gc:
    problemas_encontrados.append(f"⚠️  {len(sin_desc_gc)} experiencias sin descripcion_giftcard")
    for exp in sin_desc_gc:
        print(f"   - {exp.get('nombre', 'SIN NOMBRE')} (ID: {exp.get('id', 'SIN ID')})")

# 4. Experiencias con imagen URL vacía
sin_imagen_url = [exp for exp in experiencias if not exp.get('imagen')]
if sin_imagen_url:
    problemas_encontrados.append(f"⚠️  {len(sin_imagen_url)} experiencias sin imagen (se usará ícono)")
    for exp in sin_imagen_url:
        print(f"   - {exp.get('nombre', 'SIN NOMBRE')}")

# 5. Experiencias sin precio
sin_precio = [exp for exp in experiencias if not exp.get('monto_fijo') and not exp.get('montos_sugeridos')]
if sin_precio:
    problemas_encontrados.append(f"❌ {len(sin_precio)} experiencias sin precio")
    for exp in sin_precio:
        print(f"   - {exp.get('nombre', 'SIN NOMBRE')} (ID: {exp.get('id', 'SIN ID')})")

if not problemas_encontrados:
    print("\n✅ No se detectaron problemas en los datos")
else:
    print("\nResumen de problemas:")
    for problema in problemas_encontrados:
        print(f"  {problema}")

# Test de simulación del JavaScript
print(f"\n{'=' * 80}")
print("SIMULACIÓN DEL CÓDIGO JAVASCRIPT")
print(f"{'=' * 80}")

# Simular: const experiencias = {{ experiencias|safe }};
print(f"\nJavaScript recibiría:")
print(f"  const experiencias = {json.dumps(experiencias, ensure_ascii=False)};")

# Simular: exp = experiencias.find(e => e.id === 'tinas')
test_id = 'tinas'
found_exp = next((e for e in experiencias if e.get('id') == test_id), None)
if found_exp:
    print(f"\n✅ experiencias.find(e => e.id === '{test_id}') → Encontrado")
    print(f"   Nombre: {found_exp.get('nombre')}")
    print(f"   Monto: {found_exp.get('monto_fijo', found_exp.get('montos_sugeridos'))}")
else:
    print(f"\n❌ experiencias.find(e => e.id === '{test_id}') → undefined")
    print(f"   El JavaScript no podrá seleccionar esta experiencia!")

print(f"\n{'=' * 80}")
print("FIN DE LA PRUEBA")
print(f"{'=' * 80}\n")
