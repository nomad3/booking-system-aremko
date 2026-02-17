import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

print("=== VERIFICAR TODAS LAS TABLAS DEL CALENDARIO ===\n")

cursor = connection.cursor()

# Lista de tablas y columnas que el calendario podría usar
tablas_requeridas = {
    'ventas_serviciobloqueo': [
        'id', 'servicio_id', 'fecha', 'fecha_inicio', 'fecha_fin',
        'motivo', 'hora_slot', 'created_at', 'updated_at', 'activo'
    ],
    'ventas_servicioslotbloqueo': [
        'id', 'servicio_id', 'fecha', 'hora_slot', 'motivo',
        'created_at', 'updated_at', 'activo'
    ],
    'ventas_ventareserva': [
        'id', 'cliente_id', 'fecha', 'hora', 'estado',
        'created_at', 'updated_at'
    ],
    'ventas_servicio': [
        'id', 'nombre', 'precio_base', 'activo',
        'created_at', 'updated_at'
    ]
}

problemas_encontrados = []

for tabla, columnas_esperadas in tablas_requeridas.items():
    print(f"\n{'='*50}")
    print(f"Verificando tabla: {tabla}")
    print('='*50)

    # Verificar si la tabla existe
    cursor.execute(f"""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = '{tabla}'
        )
    """)
    existe = cursor.fetchone()[0]

    if not existe:
        print(f"❌ La tabla {tabla} NO EXISTE")
        problemas_encontrados.append(f"Tabla {tabla} no existe")
        continue

    print(f"✅ La tabla existe")

    # Obtener columnas actuales
    cursor.execute(f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = '{tabla}'
        ORDER BY column_name
    """)
    columnas_actuales = [col[0] for col in cursor.fetchall()]
    print(f"\nColumnas actuales: {columnas_actuales}")

    # Verificar columnas faltantes
    columnas_faltantes = [col for col in columnas_esperadas if col not in columnas_actuales]

    if columnas_faltantes:
        print(f"\n❌ Columnas faltantes: {columnas_faltantes}")
        for col in columnas_faltantes:
            problemas_encontrados.append(f"Tabla {tabla} falta columna: {col}")
    else:
        print("\n✅ Todas las columnas esperadas están presentes")

# Resumen
print(f"\n\n{'='*50}")
print("RESUMEN DE PROBLEMAS ENCONTRADOS")
print('='*50)

if problemas_encontrados:
    print("\n❌ Se encontraron los siguientes problemas:")
    for i, problema in enumerate(problemas_encontrados, 1):
        print(f"   {i}. {problema}")

    print("\n\nPara arreglar estos problemas, puedes ejecutar:")
    print("- python fix_calendar_model_issue.py")
    print("- python fix_servicioslotbloqueo_created_at.py")
    print("\nO crear un script personalizado para los problemas específicos.")
else:
    print("\n✅ No se encontraron problemas. El calendario debería funcionar correctamente.")

print("\n=== FIN DE VERIFICACIÓN ===")